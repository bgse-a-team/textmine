"""
(c) 2015, Stephen Hansen, stephen.hansen@upf.edu
"""

#from __future__ import division

import codecs
import itertools
import numpy as np
import pandas as pd
# Uncomment for web applications/servers
# import matplotlib
# matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import dendrogram, linkage

from topicmodels.samplers import samplers_lda


class LDAGibbs():

    def __init__(self, docs, K):

        """
        Initialize a topic model for Gibbs sampling.
        docs: list (documents) of lists (string tokens within documents)
        K: number of topics
        """

        self.K = K
        self.D = len(docs)
        self.docs = docs

        doc_list = list(itertools.chain(*docs))
        self.token_key = {}
        for i, v in enumerate(set(doc_list)):
            self.token_key[v] = i
        self.V = len(self.token_key)

        self.tokens = np.array([self.token_key[t] for t in doc_list],
                               dtype=np.int)
        self.N = self.tokens.shape[0]
        self.topic_seed = np.random.random_integers(0, K-1, self.N)

        self.docid = [[i]*len(d) for i, d in enumerate(docs)]
        self.docid = np.array(list(itertools.chain(*self.docid)), dtype=np.int)

        self.alpha = 50/self.K
        self.beta = 200/self.V

    def set_priors(self, alpha, beta):

        """
        Override default values for Dirichlet hyperparameters.
        alpha: hyperparameter for distribution of topics within documents.
        beta: hyperparameter for distribution of tokens within topics.
        """

        assert type(alpha) == float and type(beta) == float

        self.alpha = alpha
        self.beta = beta

    def set_seed(self, seed):

        """
        Override default values for random initial topic assignment,
        set to "seed" instead.
        """

        assert seed.dtype == np.int and seed.shape == (self.N,)
        self.topic_seed = seed

    def set_sampled_topics(self, sampled_topics):

        """
        Allocate sampled topics to the documents rather than estimate them.
        Automatically generate term-topic and document-topic matrices.
        """

        assert sampled_topics.dtype == np.int and \
            len(sampled_topics.shape) <= 2

        if len(sampled_topics.shape) == 1:
            self.sampled_topics = \
                sampled_topics.reshape(1, sampled_topics.shape[0])
        else:
            self.sampled_topics = sampled_topics

        self.samples = self.sampled_topics.shape[0]

        self.tt = self.tt_comp(self.sampled_topics)
        self.dt = self.dt_comp(self.sampled_topics)

    def sample(self, burnin, thinning, samples, append=True):

        """
        Estimate topics via Gibbs sampling.
        burnin: number of iterations to allow chain to burn in before sampling.
        thinning: thinning interval between samples.
        samples: number of samples to take.
        Total number of samples = burnin + thinning * samples
        If sampled topics already exist and append = True, extend chain from
        last sample.
        If append = False, start new chain from the seed.
        """

        if hasattr(self, 'sampled_topics') and append:

            sampled_topics = \
                samplers_lda.sampler(self.docid, self.tokens,
                                     self.sampled_topics[self.samples-1, :],
                                     self.N, self.V, self.K, self.D,
                                     self.alpha, self.beta,
                                     burnin, thinning, samples)

            tt_temp = self.tt_comp(sampled_topics)
            dt_temp = self.dt_comp(sampled_topics)

            self.sampled_topics = \
                np.concatenate((self.sampled_topics, sampled_topics))
            self.tt = np.concatenate((self.tt, tt_temp), axis=2)
            self.dt = np.concatenate((self.dt, dt_temp), axis=2)

            self.samples = self.samples + samples

        else:

                self.samples = samples

                seed = np.copy(self.topic_seed)

                self.sampled_topics = \
                    samplers_lda.sampler(self.docid, self.tokens, seed,
                                         self.N, self.V, self.K, self.D,
                                         self.alpha, self.beta,
                                         burnin, thinning, self.samples)

                self.tt = self.tt_comp(self.sampled_topics)
                self.dt = self.dt_comp(self.sampled_topics)

    def dt_comp(self, sampled_topics):

        """
        Compute document-topic matrix from sampled_topics.
        """

        samples = sampled_topics.shape[0]
        dt = np.zeros((self.D, self.K, samples))

        for s in range(samples):
                dt[:, :, s] = \
                    samplers_lda.dt_comp(self.docid, sampled_topics[s, :],
                                         self.N, self.K, self.D, self.alpha)

        return dt

    def tt_comp(self, sampled_topics):

        """
        Compute term-topic matrix from sampled_topics.
        """

        samples = sampled_topics.shape[0]
        tt = np.zeros((self.V, self.K, samples))

        for s in range(samples):
            tt[:, :, s] = \
                samplers_lda.tt_comp(self.tokens, sampled_topics[s, :],
                                     self.N, self.V, self.K, self.beta)

        return tt

    def topic_content(self, W, output_file="topic_description.csv"):

        """
        Print top W words in each topic to file.
        """

        topic_top_probs = []
        topic_top_words = []

        tt = self.tt_avg(False)

        for t in range(self.K):
            top_word_indices = tt[:, t].argsort()[-W:][::-1]
            topic_top_probs.append(np.round(np.sort(tt[:, t])[-W:][::-1], 3))
            topic_top_words.append([self.token_key.keys()
                                   [self.token_key.values().index(i)]
                                   for i in top_word_indices])

        with codecs.open(output_file, "w", "utf-8") as f:
            for t in range(self.K):
                words = ','.join(topic_top_words[t])
                probs = ','.join([str(i) for i in topic_top_probs[t]])
                f.write("topic" + str(t) + ',')
                f.write("%s\n" % words)
                f.write(" " + ',')
                f.write("%s\n" % probs)

    def perplexity(self):

        """
        Compute perplexity for each sample.
        """

        return samplers_lda.perplexity_comp(self.docid, self.tokens,
                                            self.tt, self.dt, self.N,
                                            self.K, self.samples)

    def samples_keep(self, index):

        """
        Keep subset of samples.  If index is an integer, keep last N=index
        samples.  If index is a list, keep the samples
        corresponding to the index values in the list.
        """

        if isinstance(index, (int, long)):
            index = range(self.samples)[-index:]

        self.sampled_topics = np.take(self.sampled_topics, index, axis=0)
        self.tt = np.take(self.tt, index, axis=2)
        self.dt = np.take(self.dt, index, axis=2)

        self.samples = len(index)

    def tt_avg(self, print_output=True, output_file="tt.csv"):

        """
        Compute average term-topic matrix, and print to file if
        print_output=True.
        """

        avg = self.tt.mean(axis=2)
        if print_output:
            np.savetxt(output_file, avg, delimiter=",")
        return avg

    def dt_avg(self, print_output=True, output_file="dt.csv"):

        """
        Compute average document-topic matrix, and print to
        file if print_output=True.
        """

        avg = self.dt.mean(axis=2)
        if print_output:
            np.savetxt(output_file, avg, delimiter=",")
        return avg

    def dict_print(self, output_file="dict.csv"):

        """
        Print mapping from tokens to numeric indices.
        """

        with codecs.open(output_file, "w", encoding='utf-8') as f:
                for (v, k) in self.token_key.items():
                    f.write("%s,%d\n" % (v, k))

    def dendrogram(self, data=None):
        """
        Return a matplotlib plt object and the dendrogram matrix
        data must be a DxK matrix of term topic distribution
        """
        if data is None:
            print('Note: Using the average of the tt matrices')
            print('To use a specific tt matrix,\
run self.dendrogram(data=tt[1,:,:])')
            data = self.tt_avg().T

        def augmented_dendrogram(*args, **kwargs):
            ddata = dendrogram(*args, **kwargs)
            dcoords = pd.DataFrame(ddata['dcoord']).replace({0: np.nan})
            minimum = dcoords.min().min()
            maximum = dcoords.max().max()

            if not kwargs.get('no_plot', False):
                for i, d in zip(ddata['icoord'], ddata['dcoord']):
                    x = 0.5 * sum(i[1:3])
                    y = d[1]
                    # plt.plot(x, y, 'ro')
                    # plt.annotate("%.3g" % y, (x, y), xytext=(0, -8),
                    #              textcoords='offset points',
                    #              va='top', ha='center')
                    plt.ylim(ymin=minimum*0.95, ymax=maximum*1.05)
                    return ddata

        def hellinger(u, v):
            np.sqrt(((np.sqrt(u)-np.sqrt(v))**2).sum())/float(np.sqrt(2))

        linkage_matrix = linkage(data, method="single", metric=hellinger)

        plt.figure(1, figsize=(10, 4))
        plt.clf()

        plt.subplot(1, 1, 1)
        ddata = augmented_dendrogram(linkage_matrix,
                                     color_threshold=1,
                                     p=data.shape[0],
                                     truncate_mode='lastp',
                                     show_leaf_counts=True,
                                     )

        # Get the top words in topic as x axis labels
        topic_top_words = []

        tt = data.T

        for t in range(self.K):
            top_word_indices = tt[:, t].argsort()[-3:][::-1]
            topic_top_words.append([self.token_key.keys()
                                   [self.token_key.values().index(i)]
                                   for i in top_word_indices])

        new_labels = [' '.join(topic_top_words[el])+' '+str(el)
                      for el in ddata['leaves']]
        plt.xticks(plt.xticks()[0], new_labels,
                   rotation=40, ha='right')
        plt.tight_layout(pad=1)
        plt.title("Dendrogram")
        return plt, ddata


class QueryGibbs():

    def __init__(self, docs, token_key, tt):

        """
        Class for querying out-of-sample documents given output
        of estimated LDA model.
        docs: list (documents) of lists
        (string tokens within documents)
        token_key: mapping from tokens to numeric indices
        (tokens in docs not in key stripped out)
        tt: 3-d array of estimated topics (number of tokens in topic
        model x number of topics x number of samples)
        """

        assert len(token_key) == tt.shape[0]

        ldatokens = set(token_key.keys())

        def keep(tokens):
            return [t for t in tokens if t in ldatokens]
        self.docs = map(keep, docs)

        self.D = len(self.docs)
        self.tt = tt
        self.V = tt.shape[0]
        self.K = tt.shape[1]
        self.samples = tt.shape[2]

        doc_list = list(itertools.chain(*self.docs))
        self.tokens = np.array([token_key[t] for t in doc_list],
                               dtype=np.int)
        self.N = self.tokens.shape[0]
        self.topic_seed = \
            np.random.random_integers(0, self.K-1, size=self.N)

        self.docid = [[i]*len(d) for i, d in enumerate(self.docs)]
        self.docid = np.array(list(itertools.chain(*self.docid)),
                              dtype=np.int)

        self.alpha = 50/self.K

    def set_priors(self, alpha):

        """
        Override default value for Dirichlet hyperparameter.
        alpha: hyperparameter for distribution of topics within documents.
        """

        assert type(alpha) == float
        self.alpha = alpha

    def set_seed(self, seed):

        """
        Override default values for random initial topic assignment,
        set to "seed" instead.
        seed is 2-d array (number of samples in LDA model x number
        of tokens in LDA model)
        """

        assert seed.dtype == np.int and seed.shape == (self.samples, self.N)
        self.topic_seed = seed

    def query(self, query_samples):

        """
        Query docs with query_samples number of Gibbs
        sampling iterations.
        """

        self.sampled_topics = np.zeros((self.samples, self.N),
                                       dtype=np.int)

        for s in range(self.samples):

            self.sampled_topics[s, :] = \
                samplers_lda.sampler_query(self.docid, self.tokens,
                                           self.topic_seed,
                                           np.ascontiguousarray(
                                               self.tt[:, :, s],
                                               dtype=np.float),
                                           self.N, self.K, self.D,
                                           self.alpha, query_samples)

            print("Sample %d queried" % s)

        self.dt = np.zeros((self.D, self.K, self.samples))

        for s in range(self.samples):
            self.dt[:, :, s] = \
               samplers_lda.dt_comp(self.docid, self.sampled_topics[s, :],
                                    self.N, self.K, self.D, self.alpha)

    def perplexity(self):

        """
        Compute perplexity for each sample.
        """

        return samplers_lda.perplexity_comp(self.docid, self.tokens,
                                            self.tt, self.dt, self.N,
                                            self.K, self.samples)

    def dt_avg(self, print_output=True, output_file="dt_query.csv"):

        """
        Compute average document-topic matrix,
        and print to file if print_output=True.
        """

        avg = self.dt.mean(axis=2)
        if print_output:
            np.savetxt(output_file, avg, delimiter=",")
        return avg
