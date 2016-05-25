#!/usr/bin/python
"""Extracts TF-IDF from recipes DB."""

import json
from nltk.tokenize import RegexpTokenizer
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet

import re

from sklearn.feature_extraction.text import TfidfVectorizer

import numpy as np
import pandas as pd


class WordAccepter(object):
    """This class is filtering acceptable words through their hypernyms."""

    def __init__(self, wrong_words):
        """Initalize the forbidden words and the lemmatizer."""
        self.result_cache = {}
        self.wrong_words = set(wrong_words)
        self.lemmatize = WordNetLemmatizer().lemmatize

    def is_word_acceptable(self, word, v=False):
        """
        Return true if a word can't be rejected.

        Check a word's hypernyms and test them against a list of forbidden
        words: A word is acceptable if none of its hypernyms are in
        the forbidden list.
        """
        compute_word = True
        if word in self.result_cache:
            compute_word = v
            acceptable_word = self.result_cache[word]
        if compute_word:
            acceptable_word = True
            try:
                stem = self.lemmatize(word)
                synset = wordnet.synset(stem + '.n.01')
                for path in synset.hypernym_paths():
                    for hypernym in path:
                        for wrong_word in self.wrong_words:
                            if wrong_word in hypernym.name():
                                acceptable_word = False
                                break
                if v:
                    if not acceptable_word:
                        print 'No that\'s not a correct word!'
                    print synset.hypernym_paths()
            except Exception as e:
                if v:
                    print 'Exception: ' + e.message
                acceptable_word = False
            self.result_cache[word] = acceptable_word
        return acceptable_word


def read_recipes_file(filename, max_documents=None, filter_words=None,
                      accepter=None, equalize=True):
    """
    Read and parse a recipes file.

    Read a recipes file and returns a DataFrame with "Name" and "Keywords".
    Args:
        max_documents:  maximum number of documents to be saved.
        filter_words:   only documents having one of those word in the title
                        will be considered.
    """
    recipes = pd.DataFrame()
    recipes_names = list()
    recipes_ingredients = list()

    lemmatize = WordNetLemmatizer().lemmatize
    tokenize = RegexpTokenizer(r'\w+').tokenize

    refused_words = set()

    if max_documents is None:
        max_documents = 1000
    if filter_words is None:
        filter_words = []
    filter_words_count = np.zeros(len(filter_words), dtype='int')
    if len(filter_words) > 0 and equalize:
        max_filter_words_count = np.zeros_like(filter_words_count)
        average_recipes = max_documents / len(filter_words)
        extra_recipes = max_documents % len(filter_words)
        for i, filter_word in enumerate(filter_words):
            actual_recipes = average_recipes
            if i < extra_recipes:
                actual_recipes += 1
            max_filter_words_count[i] = actual_recipes

    with open(filename, 'r') as file_recipe:
        for line in file_recipe:
            if len(recipes_names) >= max_documents:
                break
            recipe = json.loads(line)
            title = recipe['name'].lower()
            title_filtered = []
            for word in tokenize(title):
                if re.match("^[a-zA-Z_]*$", word):
                    title_filtered.append(word)
            if len(title_filtered) <= 0:
                continue
            title_filtered = ' '.join(title_filtered)
            title_is_ok = True

            temp_filter_words_count = np.zeros_like(filter_words_count)

            if filter_words is not None and len(filter_words) > 0:
                title_is_ok = False
                # Verify that the title contains at least one filter word
                for i, word in enumerate(filter_words):
                    if word in title_filtered:
                        if equalize:
                            max_occurences = max_filter_words_count[i]
                            if filter_words_count[i] < max_occurences:
                                title_is_ok = True
                                temp_filter_words_count[i] += 1
                        else:
                            title_is_ok = True
                            temp_filter_words_count[i] += 1
            if title_is_ok:
                # We can then verify the ingredients
                ingredients_filtered = set()
                ingredients = recipe['ingredients'].lower()
                for line_ingredient in ingredients.split("\n"):
                    # Rejects wrong ingredients
                    for word in tokenize(line_ingredient):
                        acceptable_word = True
                        if len(word) <= 2:
                            acceptable_word = False
                        if not re.match("^[a-zA-Z_]*$", word):
                            acceptable_word = False
                        if acceptable_word:
                            stem = lemmatize(word)
                            acceptable_word = accepter.is_word_acceptable(stem)
                            if acceptable_word:
                                ingredients_filtered.add(stem)
                            else:
                                refused_words.add(word)
                # If there are enough ingredients left, we add the recipe
                if len(ingredients_filtered) >= 3:
                    recipes_names.append(title_filtered)
                    str_ingredients_filtered = ' '.join(ingredients_filtered)
                    recipes_ingredients.append(str_ingredients_filtered)
                    filter_words_count += temp_filter_words_count

    n_recipes = len(recipes_names)
    for i, word in enumerate(filter_words):
        n_occurences = filter_words_count[i]
        print 'There are ' + str(n_occurences) + ' occurences of the ' + \
              'word \"' + word + '\" (' + str(n_occurences * 100. /
                                              n_recipes) + '%)'
    if len(filter_words) > 0:
        filter_words_count_total = np.sum(filter_words_count)
        redundancy = (filter_words_count_total - n_recipes) / float(n_recipes)
        print 'There are ' + str(len(recipes_names)) + ' recipes, and ' + \
              'therefore ' + str(redundancy * 100) + '% redundancy ' + \
              'between words.'
    else:
        print 'There are ' + str(len(recipes_names)) + ' recipes'

    recipes['Name'] = recipes_names
    recipes['Keywords'] = recipes_ingredients

    return recipes


def main(max_documents=1000, filter_words=None, wrong_words=None,
         equalize=True):
    """Launch a TF-IDF vectorizer on a recipes file after parsing it."""
    if wrong_words is None:
        wrong_words = ['container', 'unit', 'concept', 'property',
                       'person', 'instrument']
    accepter = WordAccepter(wrong_words)

    recipes = read_recipes_file('recipeitems-latest.json',
                                max_documents=max_documents,
                                filter_words=filter_words, accepter=accepter,
                                equalize=equalize)
    recipes.to_pickle('recipes.pkl')

    tfidf = TfidfVectorizer()
    matrix = tfidf.fit_transform(list(recipes['Keywords']))
    matrix = matrix.todense()
    np.save('features_exercise3.npy', matrix)


if __name__ == "__main__":
    main(filter_words=['fish', 'chocolate'])
