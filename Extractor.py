import pandas as pd
from time import time
from tqdm import tqdm

from Trie import Trie
from Cleaner import Cleaner
from Entropy import calculate_entropy, cal_pmi


class Extractor(object):

    def __init__(self, rfpath, max_len=4):
        self.prefixTree = Trie()
        self.suffixTree = Trie(direction='suffix')

        self.vocabulary = []
        self.len_dict = dict()
        # 想要计n个字的词必须用n+1-gram
        self.max_len = max_len + 1

        text = Cleaner.preprocess_text(rfpath)
        self.buildTreesAndDics(text)
        self.prefixTree.set_entropy()
        self.suffixTree.set_entropy()

        self.words = dict()

    def buildTreesAndDics(self, text):
        tic = time()

        pbar = tqdm(range(self.max_len))
        for i in pbar:
            pbar.set_description("buildTreesAndDics, %d-gram \n" % (i + 1))
            n_gram_list = sum(
                map(lambda x: Cleaner.n_gram(x, i + 1), text), [])
            self.len_dict[i + 1] = len(n_gram_list)
            if i >= 1:
                self.vocabulary.extend(list(set(n_gram_list)))
            for word in n_gram_list:
                self.prefixTree.insert(word, i + 1)
                self.suffixTree.insert(word, i + 1)
        print("build tree done! %.2fs" % (time() - tic))

    def score(self, candidate):
        '''
        淘宝
        h_r_l:宝的左信息熵
        h_l_r:淘的右信息熵
        '''
        children = set()
        h_l, count = calculate_entropy(
            candidate, self.prefixTree, return_count=True)
        h_r = calculate_entropy(candidate, self.suffixTree, return_count=False)
        max_score = 0
        for seg_index in range(1, len(candidate)):
            pmi = cal_pmi(candidate, self.len_dict, seg_index, self.suffixTree)

            left_candidate = candidate[:seg_index]
            right_candidate = candidate[seg_index:]

            if left_candidate in self.words:
                children.add(left_candidate)
            if right_candidate in self.words:
                children.add(right_candidate)

            h_r_l = calculate_entropy(
                right_candidate, self.prefixTree, return_count=False)
            h_l_r = calculate_entropy(
                left_candidate, self.suffixTree, return_count=False)
            score = min(h_l_r, h_r_l)
            if score > max_score:
                max_score = score
                
        if h_l == 0 or h_r == 0:
            return count, 0, 0

        max_score = pmi + min(h_l, h_r) - max_score

        for child in children:
            # 出现次数大于等于子段，选长的
            if count >= self.words[child]['count']:
                del self.words[child]
            elif max_score < self.words[child]['score']:
                return
            else:
                del self.words[child]
        return count, max_score, max_score * count

    def extract_words(self, thresh=None):
        # calculate PMI and freq remove dict words
        if thresh:
            for word in tqdm(self.vocabulary):
                if self.score(word):
                    count, score, final = self.score(word)
                if score > thresh:
                    self.words[word] = {"candidate": word,
                                   "count": count, "score": score, "final": final}
            words = pd.DataFrame.from_dict(list(self.words.values()))
        else:
            words = pd.DataFrame(self.vocabulary, columns=['candidate'])
            words[['count', 'score', 'final']] = words.apply(
                lambda x: pd.Series(self.score(x['candidate'])), axis=1)
        if words.shape[0]:
            words = words.sort_values(
                "final", ascending=False).reset_index(drop=True)
        return words