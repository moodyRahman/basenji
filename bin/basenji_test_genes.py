#!/usr/bin/env python
from optparse import OptionParser
import os
import sys

import h5py
import numpy as np
import tensorflow as tf

import basenji

'''
basenji_test_genes.py

Compare predicted to measured CAGE gene expression estimates.
'''

################################################################################
# main
################################################################################
def main():
    usage = 'usage: %prog [options] <params_file> <model_file> <genes_hdf5_file>'
    parser = OptionParser(usage)
    parser.add_option('-b', dest='batch_size', default=None, type='int', help='Batch size [Default: %default]')
    parser.add_option('-o', dest='out_dir', default='sed', help='Output directory for tables and plots [Default: %default]')
    parser.add_option('-t', dest='target_indexes', help='Comma-separated list of target indexes to scatter plot true versus predicted values')
    (options,args) = parser.parse_args()

    if len(args) != 3:
        parser.error('Must provide parameters and model files, and genes HDF5 file')
    else:
        params_file = args[0]
        model_file = args[1]
        genes_hdf5_file = args[2]

    if not os.path.isdir(options.out_dir):
        os.mkdir(options.out_dir)

    #################################################################
    # reads in genes HDF5

    genes_hdf5_in = h5py.File(genes_hdf5_file)

    seg_chrom = [chrom.decode('UTF-8') for chrom in genes_hdf5_in['seg_chrom']]
    seg_start = np.array(genes_hdf5_in['seg_start'])
    seg_end = np.array(genes_hdf5_in['seg_end'])
    seqs_segments = list(zip(seg_chrom,seg_start,seg_end))

    seqs_1hot = genes_hdf5_in['seqs_1hot']

    transcripts = [tx.decode('UTF-8') for tx in genes_hdf5_in['transcripts']]
    transcript_index = np.array(genes_hdf5_in['transcript_index'])
    transcript_pos = np.array(genes_hdf5_in['transcript_pos'])

    transcript_map = OrderedDict()
    for ti in range(len(transcripts)):
        transcript_map[transcripts[ti]] = (transcript_index[ti], transcript_pos[ti])

    transcript_targets = genes_hdf5_in['transcript_targets']

    target_labels = [tl.decode('UTF-8') for tl in genes_hdf5_in['target_labels']


    #################################################################
    # setup model

    job = basenji.dna_io.read_job_params(params_file)

    job['batch_length'] = seqs_1hot.shape[1]
    job['seq_depth'] = seqs_1hot.shape[2]

    if 'num_targets' not in job:
        print("Must specify number of targets (num_targets) in the parameters file. I know, it's annoying. Sorry.", file=sys.stderr)
        exit(1)

    # build model
    dr = basenji.rnn.RNN()
    dr.build(job)

    if options.batch_size is not None:
        dr.batch_size = options.batch_size


    #################################################################
    # predict

    # initialize batcher
    batcher = basenji.batcher.Batcher(seqs_1hot, batch_size=dr.batch_size)

    # initialie saver
    saver = tf.train.Saver()

    with tf.Session() as sess:
        # load variables into session
        saver.restore(sess, model_file)

        # predict
        seq_preds = dr.predict(sess, batcher)


    #################################################################
    # convert to gene-based predictions
    t0 = time.time()

    # initialize target predictions
    transcript_preds = np.zeros((len(transcript_map), seq_preds.shape[2]))

    tx_i = 0
    for transcript in transcript_map:
        seg_i, seg_pos = transcript_map[transcript]
        transcript_preds[tx_i,:] = seqs_preds[seg_i,seg_pos,:]
        tx_i += 1


    #################################################################
    # print and plot

    if options.target_indexes is None:
        options.target_indexes = range(seq_preds.shape[2])
    else:
        options.target_indexes = options.target_indexes.split(',')

    table_out = open('%s/table.txt' % options.out_dir, 'w')
    for ti in options.target_indexes:
        # plot scatter
        out_pdf = '%s/t%d.pdf' % (options.out_dir, ti)
        basenji.plots.jointplot(transcript_targets[:,ti], transcript_preds[:,ti], out_pdf)

        # print table lines
        for tx_i in range(len(transcripts)):
            # print transcript line
            cols = [transcripts[tx_i], transcript_targets[tx_i,ti], transcript_preds[tx_i,ti], ti, target_labels[ti]]
            print('%-20s  %.3f  %.3f  %4d  %20s' % cols, file=table_out)

    table_out.close()


    #################################################################
    # clean up

    genes_hdf5_in.close()


################################################################################
# __main__
################################################################################
if __name__ == '__main__':
    main()