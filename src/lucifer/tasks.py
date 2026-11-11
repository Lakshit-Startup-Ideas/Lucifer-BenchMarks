"""The task set. Every task has hidden tests, a reference solution that passes them, and a plausible naive solution that does not.

The naive solution is what a careless model writes. Keeping it next to the reference lets a test prove that every task's tests really
tell the two apart. Splits: "exp" (experience), "sim" (same pitfall, new problem), "xfer" (pitfalls mixed in a new way).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    id: str
    family: str  # the pitfall family; "mixed" for transfer tasks
    split: str  # exp | sim | xfer
    entry: str  # function name
    spec: str  # what the model is asked to write
    tests: tuple[str, ...]  # assert statements, run against the candidate
    reference: str
    naive: str

    @property
    def prompt(self) -> str:
        return (
            f"Write a Python function `{self.entry}`.\n\n{self.spec}\n\n"
            "Reply with the complete function in one ```python code block and nothing else."
        )


def _t(id, family, split, entry, spec, tests, reference, naive) -> Task:
    return Task(id, family, split, entry, spec, tuple(tests), reference.strip("\n"), naive.strip("\n"))


TASKS: tuple[Task, ...] = (
    # ---- empty input -----------------------------------------------------------------------------------------------------------
    _t("empty-1", "empty", "exp", "mean", "`mean(nums)` returns the arithmetic mean of a list of numbers, and 0.0 for an empty list.",
       ["assert mean([1, 2, 3]) == 2", "assert mean([]) == 0.0", "assert mean([5]) == 5"],
       "def mean(nums):\n    return sum(nums) / len(nums) if nums else 0.0",
       "def mean(nums):\n    return sum(nums) / len(nums)"),
    _t("empty-2", "empty", "exp", "first_word", "`first_word(s)` returns the first whitespace-separated word of a string, or an empty string if there is none.",
       ["assert first_word(' hello world') == 'hello'", "assert first_word('') == ''", "assert first_word('   ') == ''"],
       "def first_word(s):\n    parts = s.split()\n    return parts[0] if parts else ''",
       "def first_word(s):\n    return s.split()[0]"),
    _t("empty-3", "empty", "exp", "longest", "`longest(words)` returns the longest word in a list (the first one if several tie), or None for an empty list.",
       ["assert longest(['a', 'bb', 'cc']) == 'bb'", "assert longest([]) is None", "assert longest(['x']) == 'x'"],
       "def longest(words):\n    return max(words, key=len) if words else None",
       "def longest(words):\n    return max(words, key=len)"),
    _t("empty-4", "empty", "sim", "last_item", "`last_item(items, default=None)` returns the last item of a list, or `default` if the list is empty.",
       ["assert last_item([1, 2, 3]) == 3", "assert last_item([]) is None", "assert last_item([], 9) == 9"],
       "def last_item(items, default=None):\n    return items[-1] if items else default",
       "def last_item(items, default=None):\n    return items[-1]"),
    _t("empty-5", "empty", "sim", "min_max", "`min_max(nums)` returns a tuple (smallest, largest) of a list of numbers, and (None, None) for an empty list.",
       ["assert min_max([3, 1, 2]) == (1, 3)", "assert min_max([]) == (None, None)", "assert min_max([4]) == (4, 4)"],
       "def min_max(nums):\n    return (min(nums), max(nums)) if nums else (None, None)",
       "def min_max(nums):\n    return (min(nums), max(nums))"),
    # ---- inclusive ranges ------------------------------------------------------------------------------------------------------
    _t("range-1", "range", "exp", "sum_range", "`sum_range(a, b)` returns the sum of the integers from a to b, including both a and b, and 0 if a is greater than b.",
       ["assert sum_range(1, 4) == 10", "assert sum_range(3, 3) == 3", "assert sum_range(5, 2) == 0"],
       "def sum_range(a, b):\n    return sum(range(a, b + 1))",
       "def sum_range(a, b):\n    return sum(range(a, b))"),
    _t("range-2", "range", "exp", "count_multiples", "`count_multiples(a, b, k)` returns how many multiples of k lie between a and b, including both ends (k is positive).",
       ["assert count_multiples(1, 10, 3) == 3", "assert count_multiples(3, 9, 3) == 3", "assert count_multiples(4, 4, 2) == 1"],
       "def count_multiples(a, b, k):\n    return sum(1 for n in range(a, b + 1) if n % k == 0)",
       "def count_multiples(a, b, k):\n    return sum(1 for n in range(a, b) if n % k == 0)"),
    _t("range-3", "range", "exp", "days_between", "`days_between(start, end)` takes two integer day numbers and returns how many days there are from start to end counting both the first and the last day, and 0 if end is before start.",
       ["assert days_between(1, 1) == 1", "assert days_between(1, 7) == 7", "assert days_between(5, 1) == 0"],
       "def days_between(start, end):\n    return end - start + 1 if end >= start else 0",
       "def days_between(start, end):\n    return end - start"),
    _t("range-4", "range", "sim", "sum_squares", "`sum_squares(a, b)` returns the sum of the squares of the integers from a to b, including both a and b.",
       ["assert sum_squares(1, 3) == 14", "assert sum_squares(2, 2) == 4", "assert sum_squares(0, 4) == 30"],
       "def sum_squares(a, b):\n    return sum(i * i for i in range(a, b + 1))",
       "def sum_squares(a, b):\n    return sum(i * i for i in range(a, b))"),
    _t("range-5", "range", "sim", "count_in_range", "`count_in_range(nums, lo, hi)` returns how many numbers in the list are at least lo and at most hi (both ends count).",
       ["assert count_in_range([1, 5, 10], 1, 10) == 3", "assert count_in_range([2, 4], 4, 4) == 1", "assert count_in_range([], 0, 1) == 0"],
       "def count_in_range(nums, lo, hi):\n    return sum(1 for n in nums if lo <= n <= hi)",
       "def count_in_range(nums, lo, hi):\n    return sum(1 for n in nums if lo < n < hi)"),
    # ---- ties and ordering -----------------------------------------------------------------------------------------------------
    _t("order-1", "order", "exp", "dedupe", "`dedupe(items)` removes duplicates from a list and keeps the order in which each item first appeared.",
       ["assert dedupe(['pear', 'apple', 'pear', 'fig']) == ['pear', 'apple', 'fig']", "assert dedupe([]) == []", "assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]"],
       "def dedupe(items):\n    return list(dict.fromkeys(items))",
       "def dedupe(items):\n    return sorted(set(items))"),
    _t("order-2", "order", "exp", "sort_words", "`sort_words(words)` sorts words by length, shortest first, and alphabetically among words of the same length.",
       ["assert sort_words(['bb', 'aa', 'c']) == ['c', 'aa', 'bb']", "assert sort_words([]) == []", "assert sort_words(['b', 'a']) == ['a', 'b']"],
       "def sort_words(words):\n    return sorted(words, key=lambda w: (len(w), w))",
       "def sort_words(words):\n    return sorted(words, key=len)"),
    _t("order-3", "order", "exp", "top_frequent", "`top_frequent(words, k)` returns the k most frequent words, most frequent first; words with the same count are ordered alphabetically.",
       ["assert top_frequent(['b', 'a', 'b', 'a', 'c'], 2) == ['a', 'b']", "assert top_frequent(['x', 'y', 'y'], 1) == ['y']", "assert top_frequent([], 3) == []"],
       "def top_frequent(words, k):\n    from collections import Counter\n    c = Counter(words)\n    return sorted(c, key=lambda w: (-c[w], w))[:k]",
       "def top_frequent(words, k):\n    from collections import Counter\n    return [w for w, _ in Counter(words).most_common(k)]"),
    _t("order-4", "order", "sim", "sort_pairs", "`sort_pairs(pairs)` takes (name, score) tuples and returns them sorted by score, highest first, and by name alphabetically when scores are equal.",
       ["assert sort_pairs([('b', 1), ('a', 1), ('c', 2)]) == [('c', 2), ('a', 1), ('b', 1)]", "assert sort_pairs([]) == []", "assert sort_pairs([('z', 5)]) == [('z', 5)]"],
       "def sort_pairs(pairs):\n    return sorted(pairs, key=lambda p: (-p[1], p[0]))",
       "def sort_pairs(pairs):\n    return sorted(pairs, key=lambda p: -p[1])"),
    _t("order-5", "order", "sim", "merge_unique", "`merge_unique(a, b)` joins two lists, drops duplicates, and keeps the order in which items first appeared.",
       ["assert merge_unique(['b', 'a'], ['a', 'c']) == ['b', 'a', 'c']", "assert merge_unique([], []) == []", "assert merge_unique([2, 1], [1, 3]) == [2, 1, 3]"],
       "def merge_unique(a, b):\n    return list(dict.fromkeys(list(a) + list(b)))",
       "def merge_unique(a, b):\n    return sorted(set(a + b))"),
    # ---- text normalisation ----------------------------------------------------------------------------------------------------
    _t("text-1", "text", "exp", "is_palindrome", "`is_palindrome(s)` says whether a string reads the same backwards, ignoring upper and lower case and ignoring every character that is not a letter or digit.",
       ["assert is_palindrome('A man, a plan, a canal: Panama') is True", "assert is_palindrome('hello') is False", "assert is_palindrome('') is True"],
       "def is_palindrome(s):\n    t = [c.lower() for c in s if c.isalnum()]\n    return t == t[::-1]",
       "def is_palindrome(s):\n    return s == s[::-1]"),
    _t("text-2", "text", "exp", "word_count", "`word_count(s)` counts the words in a string, where a word is a run of letters and digits; punctuation and spaces only separate words.",
       ["assert word_count('Hi - there') == 2", "assert word_count('a,b,c') == 3", "assert word_count('') == 0"],
       "def word_count(s):\n    import re\n    return len(re.findall(r'[A-Za-z0-9]+', s))",
       "def word_count(s):\n    return len(s.split())"),
    _t("text-3", "text", "exp", "caesar", "`caesar(s, k)` shifts every letter forward by k places in the alphabet, wrapping from z to a, keeps upper and lower case, and leaves other characters unchanged.",
       ["assert caesar('abc', 1) == 'bcd'", "assert caesar('xyz', 3) == 'abc'", "assert caesar('Hi!', 2) == 'Jk!'"],
       "def caesar(s, k):\n    out = []\n    for c in s:\n        if c.isalpha():\n            base = ord('A') if c.isupper() else ord('a')\n            out.append(chr((ord(c) - base + k) % 26 + base))\n        else:\n            out.append(c)\n    return ''.join(out)",
       "def caesar(s, k):\n    return ''.join(chr(ord(c) + k) if c.isalpha() else c for c in s)"),
    _t("text-4", "text", "sim", "normalize_spaces", "`normalize_spaces(s)` replaces every run of whitespace by a single space and removes spaces at both ends.",
       ["assert normalize_spaces('  a   b  ') == 'a b'", "assert normalize_spaces('') == ''", "assert normalize_spaces('a\\t\\nb') == 'a b'"],
       "def normalize_spaces(s):\n    return ' '.join(s.split())",
       "def normalize_spaces(s):\n    return s.replace('  ', ' ')"),
    _t("text-5", "text", "sim", "initials", "`initials(name)` turns a full name into its capital initials each followed by a dot, so 'ada king lovelace' gives 'A.K.L.'; any amount of whitespace separates names and an empty string gives an empty string.",
       ["assert initials('ada king lovelace') == 'A.K.L.'", "assert initials('ada  king') == 'A.K.'", "assert initials('') == ''"],
       "def initials(name):\n    return ''.join(w[0].upper() + '.' for w in name.split())",
       "def initials(name):\n    return ''.join(w[0].upper() + '.' for w in name.split(' '))"),
    # ---- transfer: the same pitfalls, mixed in new ways --------------------------------------------------------------------------
    _t("mixed-1", "mixed", "xfer", "average_of_range", "`average_of_range(a, b)` returns the mean of the integers from a to b, including both ends, and 0.0 if a is greater than b.",
       ["assert average_of_range(1, 4) == 2.5", "assert average_of_range(3, 3) == 3.0", "assert average_of_range(5, 1) == 0.0"],
       "def average_of_range(a, b):\n    return (a + b) / 2 if a <= b else 0.0",
       "def average_of_range(a, b):\n    return sum(range(a, b)) / len(range(a, b))"),
    _t("mixed-2", "mixed", "xfer", "most_common_or_none", "`most_common_or_none(words)` returns the most frequent word, the alphabetically first one if several tie, and None for an empty list.",
       ["assert most_common_or_none(['b', 'a', 'b', 'a']) == 'a'", "assert most_common_or_none([]) is None", "assert most_common_or_none(['x', 'y', 'y']) == 'y'"],
       "def most_common_or_none(words):\n    from collections import Counter\n    if not words:\n        return None\n    c = Counter(words)\n    return sorted(c, key=lambda w: (-c[w], w))[0]",
       "def most_common_or_none(words):\n    from collections import Counter\n    return Counter(words).most_common(1)[0][0]"),
    _t("mixed-3", "mixed", "xfer", "longest_k", "`longest_k(words, k)` returns the k longest words, longest first; words of the same length are ordered alphabetically; an empty list gives an empty list.",
       ["assert longest_k(['bb', 'a', 'aa', 'ccc'], 2) == ['ccc', 'aa']", "assert longest_k([], 2) == []", "assert longest_k(['b', 'a'], 5) == ['a', 'b']"],
       "def longest_k(words, k):\n    return sorted(words, key=lambda w: (-len(w), w))[:k]",
       "def longest_k(words, k):\n    return sorted(words, key=len, reverse=True)[:k]"),
    _t("mixed-4", "mixed", "xfer", "distinct_words", "`distinct_words(s)` counts the different words in a string, ignoring upper and lower case; a word is a run of letters and digits, and an empty string has 0.",
       ["assert distinct_words('Hello, hello world!') == 2", "assert distinct_words('') == 0", "assert distinct_words('a-b a_b') == 2"],
       "def distinct_words(s):\n    import re\n    return len({w.lower() for w in re.findall(r'[A-Za-z0-9]+', s)})",
       "def distinct_words(s):\n    return len(set(s.split()))"),
)

BY_ID = {t.id: t for t in TASKS}
FAMILIES = ("empty", "range", "order", "text")




def by_split(split: str) -> list[Task]:
    return [t for t in TASKS if t.split == split]
