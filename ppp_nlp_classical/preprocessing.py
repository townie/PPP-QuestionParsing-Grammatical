""" First step of the algorithm."""

import sys
from .preprocessingMerge import Word, mergeQuotations, mergeNamedEntityTag
from nltk.stem.wordnet import WordNetLemmatizer
from nltk.corpus import wordnet

class DependenciesTree:
    """
        One node of the parse tree.
        It is a group of words of the initial sentence.
    """
    def __init__(self, word, namedentitytag='undef', dependency='undef', child=None, parent=None):
        self.wordList = [Word(word[:word.rindex('-')],int(word[word.rindex('-')+1:]))] # words of the node
        self.namedEntityTag = namedentitytag 
        self.dependency = dependency # dependency from self to its parent
        self.child = child or [] # children of self
        self.text = "" # each node contains whole sentence
        self.parent=parent # parent of self

    def string(self):
        # Concatenation of the words of the root
        w = self.getWords()
        s=''
        # Adding the definition of the root (dot format)
        t=''
        if(self.namedEntityTag != 'O' and self.namedEntityTag != 'undef'):
            t+= " [{0}]".format(self.namedEntityTag)
        s+="\t\"{0}\"[label=\"{1}{2}\",shape=box];\n".format(self.wordList[0].word+str(self.wordList[0].index),w,t)
        # Adding definitions of the edges
        for n in self.child:
            s+="\t\"{0}\" -> \"{1}\"[label=\"{2}\"];\n".format(self.wordList[0].word+str(self.wordList[0].index),n.wordList[0].word+str(n.wordList[0].index),n.dependency)
        # Recursive calls
        for n in self.child:
            s+=n.string()
        return s

    def __str__(self):
        """
            Print dependency graph in dot format
        """
        return "digraph relations {"+"\n{0}\tlabelloc=\"t\"\tlabel=\"{1}\";\n".format(self.string(),self.text)+"}"

    def merge(self,other,mergeWords):
        """
            Merge the root of the two given trees into one single node.
            Merge the two wordList if mergeWords=True (otherwise only keep the WordList of self).
            The result is stored in node 'self'.
        """
        self.child += other.child
        for c in other.child:
            c.parent = self
        if mergeWords:
          self.wordList = other.wordList + self.wordList
          self.wordList.sort(key = lambda x: x.index)
        if other.parent:
            other.parent.child.remove(other)
        other.wordList = None

    def getWords(self):
        """
            concatenate all strings of the node (in wordList)
        """
        self.wordList.sort(key = lambda x: x.index) 
        return ' '.join(x.word for x in self.wordList)

def computeEdges(r,nameToNodes):
    """
        Compute the edges of the dependence tree.
        Take in input a piece of the result produced by StanfordNLP, and the
        map from names to nodes.
    """
    for edge in r['indexeddependencies']:
        try:
            n1 = nameToNodes[edge[1]]
        except KeyError:
            n1 = DependenciesTree(edge[1])
            nameToNodes[edge[1]] = n1
        try:
            n2 = nameToNodes[edge[2]]
        except KeyError:
            n2 = DependenciesTree(edge[2])
            nameToNodes[edge[2]] = n2
        # n1 is the parent of n2
        n1.child = n1.child+[n2]
        n2.parent = n1
        n2.dependency = edge[0]

def computeTags(r,nameToNodes):
    """
        Compute the tags of the dependence tree nodes.
        Take in input a piece of the result produced by StanfordNLP, and the
        map from names to nodes.
    """
    index=0
    # Computation of the tags of the nodes
    for word in r['words']:
        index+=1
        if word[0].isalnum() or word[0] == '$' or  word[0] == '%':
            w=word[0]+'-'+str(index) # key in the nameToNodes map
            try:
                n = nameToNodes[w]
                assert len(n.wordList) == 1
                n.wordList[0].pos = word[1]['PartOfSpeech']
                if word[1]['NamedEntityTag'] != 'O':
                    n.namedEntityTag = word[1]['NamedEntityTag']
            except KeyError:        # this node does not exists (e.g. 'of' preposition)
                pass

def initText(t,s):
    """
        Set text attribute for all nodes, with string s.
    """
    t.text = s
    for c in t.child:
        initText(c,s)

def nounify(verbWord):
    """ 
        Transform a verb to the closest noun: die -> death
        From George-Bogdan Ivanov on StackOverflow: http://stackoverflow.com/a/16752477/4110059
    """
    verb_synsets = wordnet.synsets(verbWord, pos="v")
    # Word not found
    if not verb_synsets:
        return []
    # Get all verb lemmas of the word
    verb_lemmas = [l for s in verb_synsets for l in s.lemmas() if s.name().split('.')[1] == 'v']
    # Get related forms
    derivationally_related_forms = [(l, l.derivationally_related_forms()) \
                                    for l in    verb_lemmas]
    # Filter only the nouns
    related_noun_lemmas = [l for drf in derivationally_related_forms \
                           for l in drf[1] if l.synset().name().split('.')[1] == 'n']
    # Extract the words from the lemmas
    words = [l.name() for l in related_noun_lemmas]
    len_words = len(words)
    # Build the result in the form of a list containing tuples (word, probability)
    result = [(w, float(words.count(w))/len_words) for w in set(words)]
    result.sort(key=lambda w: -w[1])
    # return the word with highest probability
    return result[0][0]

def nounifyExcept(verbWord):
    """
        Transform a verb to the closest noun: die -> death
        Hard-coded exceptions (e.g. be, have, do, bear...)
    """
    nounifyException = {
        'be' : 'identity',
        'have' : 'possession',
        'do' : 'process',
        'bear' : 'birth',
        'live' : 'residence',
        'direct' : 'director'
    }
    try:
        return nounifyException[verbWord]
    except KeyError:
        return nounify(verbWord)

def normalizeWord(word,lmtzr):
    """
        Apply lemmatization to the given word.
    """
    if(word.pos and word.pos[0] == 'N'):
        word.word=lmtzr.lemmatize(word.word,'n')
        return
    if(word.pos and word.pos[0] == 'V'):
        word.word=nounifyExcept(lmtzr.lemmatize(word.word,'v'))
        return

def normalize(t,lmtzr):
    for c in t.child:
        normalize(c,lmtzr)
    if t.namedEntityTag == 'undef':
        for w in t.wordList:
            normalizeWord(w,lmtzr)

def computeTree(r):
    """
        Compute the dependence tree.
        Take in input a piece of the result produced by StanfordNLP (if foo is this result, then r = foo['sentences'][0])
        Apply quotation and NER merging
        Return the root of the tree (word 'ROOT-0').
    """
    nameToNodes = {} # map from the original string to the node
    computeEdges(r,nameToNodes)
    computeTags(r,nameToNodes)
    tree = nameToNodes['ROOT-0']
    initText(tree,r['text'].replace('"','\\\"'))
    mergeQuotations(tree,r) # quotation merging
    mergeNamedEntityTag(tree) # NER merging
    lmtzr = WordNetLemmatizer()
    normalize(tree,lmtzr)
    return tree
