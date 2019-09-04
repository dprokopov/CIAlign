#! /usr/bin/env python

import logging
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import copy
import cropseq
import consensusSeq
import sys
import itertools
import pathlib


emptyAlignmentMessage = "We deleted so much that the alignment is gone forever. We are so sorry. You're fucked."


def FastaToArray(infile):
    '''
    Convert an alignment into a numpy array.
    Parameters
    ----------
    fasta_dict: dict
        dictionary based on a fasta file with sequence names as keys and
        sequences as values

    Returns
    -------
    arr: np.array
        2D numpy array in the same order as fasta_dict where each row
        represents a single column in the alignment and each column a
        single sequence.
    '''

    nams = []
    seqs = []
    nam = ""
    seq = ""
    with open(infile) as input:
        for line in input:
            line = line.strip()
            if line[0] == ">":
                    seqs.append(seq)
                    nams.append(nam)
                    seq = []
                    nam = line.replace(">", "")
            else:
                seq += list(line)
    seqs.append(seq)
    nams.append(nam)
    arr = np.array(seqs[1:])
    return (arr, nams[1:])


def writeOutfile(outfile, arr, nams, removed, rmfile=None):
    out = open(outfile, "w")
    if rmfile is not None:
        rm = open(rmfile, "a")
        rm.write("Removed sequences:\n")
    else:
        rm = None
    i = 0
    for nam in nams:
        if nam not in removed:
            out.write(">%s\n%s\n" % (nam, "".join(list(arr[i]))))
            i += 1
        else:
            if rm is not None:
                rm.write("%s\n" % nam)
    out.close()
    if rm is not None:
        rm.close()


def seqType(arr):
    '''
    Detects if an alignment is of nucleotides or amino acids
    '''
    seq1 = arr[0]
    nucs = set(list(consensusSeq.getNtColours().keys()))
    aas = set(list(consensusSeq.getAAColours().keys()))
    n = 0
    a = 0
    x = 0
    for s in seq1:
        s = s.upper()
        if s in nucs:
            n += 1
        if s in aas:
            a += 1
        if s not in aas and s not in nucs:
            x += 1
    counts = n, a, x
    if n == max(counts):
        return "nt"
    elif a == max(counts):
        return "aa"
    else:
        raise RuntimeError ("Majority of positions are not known nucleotides or amino acids")


def updateNams(nams, removed_seqs):
    nams2 = []
    for nam in nams:
        if nam not in removed_seqs:
            nams2.append(nam)
    return (nams2)


def checkArrLength(outfile, arr, orig_nams, removed_seqs, rmfile):
    if 0 in np.shape(arr):
        writeOutfile(outfile, arr, orig_nams, removed_seqs, rmfile)
        raise RuntimeError (emptyAlignmentMessage)
    if len(np.shape(arr)) == 1:
        raise RuntimeError ("Sequences in alignment are not the same length")


def listFonts(outfile):
    flist = matplotlib.font_manager.get_fontconfig_fonts()
    flist2 = []
    for fname in flist:
        try:
            g = matplotlib.font_manager.FontProperties(fname=fname).get_name()
            flist2.append(g)
        except:
            pass
    f = plt.figure(figsize=(3, len(flist2) / 4), dpi=200)
    a = f.add_subplot(111)
    a.set_ylim(0, len(flist2))
    a.set_xlim(0, 1)
    for i, fname in enumerate(flist2):
        a.text(0, i, fname, fontdict={'name': fname})
    a.set_axis_off()
    f.savefig(outfile, dpi=200, bbox_inches='tight')


def main():
    parser = argparse.ArgumentParser(
            description='''Improve a multiple sequence alignment''')

    parser.add_argument("--inifile", dest='inifile', type=str,
                        help='path to input alignment')
    # not to confuse with inifile :)
    parser.add_argument("--infile", dest='infile', type=str,
                        help='path to input alignment')
    parser.add_argument("--outfile_stem", dest='outfile_stem', type=str,
                        default="CIAlign",
                        help="stem for output files (including path)")

    parser.add_argument("--remove_insertions", dest="remove_insertions",
                        help="run the removeInsertions function to remove insertions",
                        action="store_true")
    parser.add_argument("--insertion_min_size", dest="insertion_min_size",
                        type=int, default=3,
                        help="minimum size insertion to remove")
    parser.add_argument("--insertion_max_size", dest="insertion_max_size",
                        type=int, default=300,
                        help="maximum size insertion to remove")
    parser.add_argument("--insertion_min_flank", dest="insertion_min_flank",
                        type=int, default=5,
                        help="minimum number of bases on either side of deleted insertions")

    parser.add_argument("--remove_short", dest="remove_short",
                        help="run the removeShort function to remove sequences with less than n non-gap positions",
                        action="store_true")
    parser.add_argument("--remove_min_length", dest="remove_min_length",
                        type=int, default=50,
                        help="minimum length sequence to remove")

    parser.add_argument("--make_consensus", dest="make_consensus",
                        action="store_true", help="run the findConsensus function to make a consensus sequence")
    parser.add_argument("--consensus_type", dest="consensus_type", type=str,
                        default="majority", help="type of consensus sequence to make")
    parser.add_argument("--consensus_keep_gaps", dest="consensus_keep_gaps",
                        action="store_true", help="keep gaps in consensus at positions where a gap is the consensus")
    parser.add_argument("--consensus_name", dest="consensus_name",
                        type=str, default="consensus",
                        help="name of consensus sequence")
    parser.add_argument("--plot_coverage", dest="plot_coverage",
                        action="store_true", help="plot the coverage as an interpolated function")

    parser.add_argument("--crop_ends", dest="crop_ends",
                        action="store_true", help="run the cropEnds function to remove badly aligned ends")
    parser.add_argument("--crop_ends_mingap", dest='crop_ends_mingap',
                        type=int, default=10,
                        help="minimum gap size to crop from ends")

    parser.add_argument("--remove_badlyaligned", dest="remove_badlyaligned",
                        action="store_true", help="run the removeBadlyAligned function to remove badly aligned sequences")
    parser.add_argument("--remove_badlyaligned_minperc", dest="remove_badlyaligned_minperc",
                        type=float, default=0.9,
                        help="minimum percentage identity to majority to not be removed")

    parser.add_argument("--remove_gaponly", dest="remove_gaponly",
                        action="store_false", help="run the removeGapOnly function to remove gap only columns from the alignment")

    parser.add_argument("--make_similarity_matrix_input", dest="make_simmatrix_input",
                        action="store_true", help="run the calculateSimilarityMatrix function to make a similarity matrix for the input alignment")
    parser.add_argument("--make_similarity_matrix_output", dest="make_simmatrix_output",
                        action="store_true", help="run the calculateSimilarityMatrix function to make a similarity matrix for the output alignment")
    parser.add_argument("--make_simmatrix_dp", dest="make_simmatrix_dp",
                        type=int, default=4, help="n decimal places for the similarity matrix (output file only)")
    parser.add_argument("--make_simmatrix_minoverlap",
                        dest="make_simmatrix_minoverlap",
                        type=int, default=1, help="minimum overlap between two sequences to have non-zero similarity in the similarity matrix")
    parser.add_argument("--make_simmatrix_keepgaps", dest="make_simmatrix_keepgaps",
                        type=bool, default=False, help="include positions with gaps in either or both sequences in the similarity matrix calculation")

    parser.add_argument("--plot_input", dest="plot_input",
                        action="store_true", help="run the drawMiniAlignment function to plot the input alignment")
    parser.add_argument("--plot_output", dest="plot_output",
                        action="store_true", help="run the drawMiniAlignment function to plot the output alignment")
    parser.add_argument("--plot_markup", dest="plot_markup",
                        action="store_true", help="run the drawMiniAlignment function to plot the changes made to the alignment")
    parser.add_argument("--plot_dpi", dest="plot_dpi",
                        type=int, default=300,
                        help="dpi for plots")
    parser.add_argument("--plot_format", dest="plot_format",
                        type=str, default='png',
                        help="plot format (png or svg)")
    parser.add_argument("--plot_width", dest="plot_width",
                        type=int, default=5,
                        help="width for plots (inches)")
    parser.add_argument("--plot_height", dest="plot_height",
                        type=int, default=3,
                        help="height for plots (inches)")

    parser.add_argument("--make_sequence_logo", dest="make_sequence_logo",
                        action="store_true", help="draw a sequence logo")
    parser.add_argument("--sequence_logo_type", dest="sequence_logo_type",
                        type=str, default='bar',
                        help="type of sequence logo - bar/text/both")
    parser.add_argument("--sequence_logo_dpi", dest="sequence_logo_dpi",
                        type=int, default=300,
                        help="dpi for sequence logo image")
    parser.add_argument("--sequence_logo_font", dest="sequence_logo_font",
                        type=str, default='monospace',
                        help="font for text sequence logo")
    parser.add_argument("--sequence_logo_nt_per_row", dest='sequence_logo_nt_per_row',
                        type=int, default=50, help="number of nucleotides or aas to show per row in the sequence logo")
    parser.add_argument("--sequence_logo_filetype", dest='sequence_logo_filetype',
                        type=str, default='png', help="output file type for sequence logo - png/jpg/svg")
    parser.add_argument("--list_fonts_only", dest='list_fonts_only',
                        action="store_true",
                        help="make a swatch showing available fonts")

    args = parser.parse_args()

    log = logging.getLogger(__name__)
    log.setLevel(logging.INFO)

    logfile = "%s_log.txt" % args.outfile_stem
    handler = logging.FileHandler(logfile)
    handler.setLevel(logging.INFO)

    # create a logging format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    rmfile = "%s_removed.txt" % args.outfile_stem
    outfile = "%s_parsed.fasta" % (args.outfile_stem)

    # add the handlers to the logger
    log.addHandler(handler)

# =============================================================================
    # # read INI file
    # args = parser.parse_args()
    # inifile = args.inifile
    # print(inifile)
    #
    # parameter = dict()
    # for line in open(inifile).readlines():
    #     if "=" in line and line[0] != ";":
    #         line = line.split("#")[0].strip().split("=")
    #         try:
    #             a = float(line[1])
    #             if a == int(a):
    #                 parameter[line[0]] = int(a)
    #             else:
    #                 parameter[line[0]] = a
    #         except:
    #             try:
    #                 parameter[line[0]] = line[1].replace('"', '')
    #             except:
    #                 parameter[line[0]] = ""
    # print(parameter)
# =============================================================================

    log.info("Initial parameters: %s" % str(args))

    if args.list_fonts_only:
        print ("list fonts")
        out = "%s_fonts.png" % args.outfile_stem
        listFonts(out)
        exit()
    # convert the input fasta file into an array and make a list of
    # sequence names so the order can be maintained
    if not args.infile:
        raise RuntimeError ("Input alignment must be provided")

    arr, nams = FastaToArray(args.infile)

    # print (arr.shape)
    # store a copy of the original array
    orig_arr = copy.copy(arr)
    orig_nams = copy.copy(nams)

    # make a dictionary to store the changes made
    markupdict = dict()

    # remember positions relative to original alignment
    relativePositions = list(range(0, len(orig_arr[0])))
    # print(relativePositions)

    removed_seqs = set()
    removed_cols = set()

    # detect if the sequence is amino acids or nucleotides
    typ = seqType(arr)

    if typ == 'aa':
        log.info("Amino acid alignment detected")
    else:
        log.info("Nucleotide alignment detected")

    rmfile = "%s_removed.txt" % args.outfile_stem
    outfile = "%s_parsed.fasta" % (args.outfile_stem)
    reset_rmfile = open(rmfile, "w")
    reset_rmfile.close()
    checkArrLength(outfile, arr, orig_nams, removed_seqs, rmfile)

    if args.crop_ends:
        print ("crop ends")
        # keep in mind that here we still have the full alignment, so we don't need any adjustments for column indicies yet
        arr, r = cropEnds(arr, nams, log, args.crop_ends_mingap, rmfile)
        # print(r)

        if arr.size == 0:
            log.error(emptyAlignmentMessage)
            sys.exit()
        markupdict['crop_ends'] = r
        checkArrLength(outfile, arr, orig_nams, removed_seqs, rmfile)

    if args.remove_badlyaligned:
        # print ("remove badly aligned")
        arr, r = removeBadlyAligned(arr, nams, args.remove_badlyaligned_minperc)
        # print(r)
        markupdict['remove_badlyaligned'] = r
        removed_seqs = removed_seqs | r
        nams = updateNams(nams, r)
        checkArrLength(outfile, arr, orig_nams, removed_seqs, rmfile)

    if args.remove_insertions:
        print ("remove insertions")
        # HERE
        arr, r = removeInsertions(arr,
                                  relativePositions,
                                  log,
                                  args.insertion_min_size,
                                  args.insertion_max_size,
                                  args.insertion_min_flank,
                                  rmfile)
        if arr.size == 0:
            log.error(emptyAlignmentMessage)
            sys.exit()
        markupdict['remove_insertions'] = r
        removed_cols = removed_cols | r
        checkArrLength(outfile, arr, orig_nams, removed_seqs, rmfile)

    if args.remove_short:
        print ("remove short")
        arr, r = removeTooShort(arr, nams, log, args.remove_min_length)
        if arr.size == 0:
            log.error(emptyAlignmentMessage)
            sys.exit()
        markupdict['remove_short'] = r
        removed_seqs = removed_seqs | r
        nams = updateNams(nams, r)
        checkArrLength(outfile, arr, orig_nams, removed_seqs, rmfile)

    if args.remove_gaponly:
        print ("remove gap only")
        # for now: run as default
        # HERE
        arr, r = removeGapOnly(arr, relativePositions, log, rmfile)
        if arr.size == 0:
            log.error(emptyAlignmentMessage)
            sys.exit()
        markupdict['remove_gaponly'] = r
        checkArrLength(outfile, arr, orig_nams, removed_seqs, rmfile)

    if args.make_simmatrix_input:
        print ("make similarity matrix input")
        outf = "%s_input_similarity.tsv" % (args.outfile_stem)
        calculateSimilarityMatrix(orig_arr, orig_nams,
                                  minoverlap=args.make_simmatrix_minoverlap,
                                  keepgaps=args.make_simmatrix_keepgaps,
                                  outfile=outf, dp=args.make_simmatrix_dp)

    if args.make_simmatrix_output:
        print ("make similarity matrix output")
        outf = "%s_output_similarity.tsv" % (args.outfile_stem)
        calculateSimilarityMatrix(arr, nams,
                                  minoverlap=args.make_simmatrix_minoverlap,
                                  keepgaps=args.make_simmatrix_keepgaps,
                                  outfile=outf, dp=args.make_simmatrix_dp)


    if args.plot_input:
        print ("plot input")
        outf = "%s_input.%s" % (args.outfile_stem, args.plot_format)
        drawMiniAlignment(orig_arr, log, orig_nams, outf, typ, args.plot_dpi,
                          args.outfile_stem, args.plot_width, args.plot_height)


    if args.plot_output:
        print ("plot output")
        outf = "%s_output.%s" % (args.outfile_stem, args.plot_format)
        drawMiniAlignment(arr, log, nams, outf, typ, args.plot_dpi,
                          args.outfile_stem, args.plot_width, args.plot_height)

    if args.plot_markup:
        print ("plot markup")
        outf = "%s_markup.%s" % (args.outfile_stem, args.plot_format)
        drawMiniAlignment(orig_arr, log, orig_nams, outf, typ, args.plot_dpi,
                          args.outfile_stem, args.plot_width, args.plot_height,
                          markup=True, markupdict=markupdict)

    if args.make_consensus:
        print ("make consensus")
        cons, coverage = consensusSeq.findConsensus(arr, log, args.consensus_type)
        consarr = np.array(cons)
        arr_plus_cons = np.row_stack((arr, consarr))
        cons = "".join(cons)
        if not args.consensus_keep_gaps:
            cons = cons.replace("-", "")
        out = open("%s_consensus.fasta" % args.outfile_stem, "w")
        out.write(">%s\n%s\n" % (args.consensus_name, cons))
        out.close()
        outf = "%s_with_consensus.fasta" % args.outfile_stem
        writeOutfile(outf, arr_plus_cons, nams + [args.consensus_name], removed_seqs)

    if args.plot_coverage:
        coverage_file = args.outfile_stem + "_coverage.png"
        if not args.make_consensus:
            cons, coverage = consensusSeq.findConsensus(arr, args.consensus_type)

        consensusSeq.makeCoveragePlot(cons, coverage, coverage_file)


    if args.make_sequence_logo:
        print ("make sequence logo")

        if args.sequence_logo_type == 'bar':
            out = "%s_logo_bar.%s" % (args.outfile_stem, args.sequence_logo_filetype)
            print (out)
            consensusSeq.sequence_bar_logo(arr, out, typ=typ,
                                           figdpi=args.sequence_logo_dpi,
                                           figrowlength=args.sequence_logo_nt_per_row)
        elif args.sequence_logo_type == 'text':
            out = "%s_logo_text.%s" % (args.outfile_stem, args.sequence_logo_filetype)
            consensusSeq.sequence_logo(arr, out, typ=typ,
                                       figdpi=args.sequence_logo_dpi,
                                       figfontname=args.sequence_logo_font,
                                       figrowlength=args.sequence_logo_nt_per_row)
        elif args.sequence_logo_type == 'both':
            out = "%s_logo_bar.%s" % (args.outfile_stem, args.sequence_logo_filetype)
            consensusSeq.sequence_bar_logo(arr, out, typ=typ,
                                           figdpi=args.sequence_logo_dpi,
                                           figrowlength=args.sequence_logo_nt_per_row)
            out = "%s_logo_text.%s" % (args.outfile_stem, args.sequence_logo_filetype)
            consensusSeq.sequence_logo(arr, out, typ=typ,
                                       figdpi=args.sequence_logo_dpi,
                                       figfontname=args.sequence_logo_font,
                                       figrowlength=args.sequence_logo_nt_per_row)

    writeOutfile(outfile, arr, orig_nams, removed_seqs, rmfile)
    # print(outfile)


if __name__ == "__main__":
    main()
