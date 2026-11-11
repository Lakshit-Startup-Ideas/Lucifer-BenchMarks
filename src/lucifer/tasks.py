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
    set: str = "pitfall"  # "pitfall" (fully specified tasks with traps) or "convention" (hidden conventions that only feedback can reveal)

    @property
    def prompt(self) -> str:
        return (
            f"Write a Python function `{self.entry}`.\n\n{self.spec}\n\n"
            "Reply with the complete function in one ```python code block and nothing else."
        )


def _t(id, family, split, entry, spec, tests, reference, naive, set="pitfall") -> Task:
    return Task(id, family, split, entry, spec, tuple(tests), reference.strip("\n"), naive.strip("\n"), set)


def _c(id, family, split, entry, spec, tests, reference, naive) -> Task:
    return _t(id, family, split, entry, spec, tests, reference, naive, set="convention")


def _raises(call: str, message: str) -> str:
    """A test statement: `call` must raise ValueError with exactly this message."""
    return f"try:\n    {call}\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == {message!r}, str(e)"


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
    # ---- harder families: several requirements at once, closed intervals, exact money, quoting, boundaries ---------------------------
    _t("interval-1", "interval", "exp", "merge_intervals", "`merge_intervals(intervals)` takes closed integer intervals as (start, end) tuples in any order and merges every pair that overlaps or shares an endpoint; it returns the merged tuples sorted by start, and an empty list for no input.",
       ["assert merge_intervals([(1, 3), (2, 6), (8, 10)]) == [(1, 6), (8, 10)]", "assert merge_intervals([(1, 3), (3, 5)]) == [(1, 5)]", "assert merge_intervals([(5, 6), (1, 2)]) == [(1, 2), (5, 6)]", "assert merge_intervals([]) == []"],
       "def merge_intervals(intervals):\n    out = []\n    for s, e in sorted(intervals):\n        if out and s <= out[-1][1]:\n            out[-1] = (out[-1][0], max(out[-1][1], e))\n        else:\n            out.append((s, e))\n    return out",
       "def merge_intervals(intervals):\n    out = []\n    for s, e in sorted(intervals):\n        if out and s < out[-1][1]:\n            out[-1] = (out[-1][0], max(out[-1][1], e))\n        else:\n            out.append((s, e))\n    return out"),
    _t("interval-2", "interval", "exp", "total_covered", "`total_covered(intervals)` takes closed integer intervals as (start, end) tuples and returns how many different integers lie inside at least one of them; an integer inside several intervals counts once, and no intervals gives 0.",
       ["assert total_covered([(1, 3), (3, 5)]) == 5", "assert total_covered([(2, 2)]) == 1", "assert total_covered([(1, 4), (2, 3)]) == 4", "assert total_covered([]) == 0"],
       "def total_covered(intervals):\n    return len({n for s, e in intervals for n in range(s, e + 1)})",
       "def total_covered(intervals):\n    return sum(e - s for s, e in intervals)"),
    _t("interval-3", "interval", "exp", "is_free", "`is_free(intervals, t)` says whether the integer t lies outside every one of the closed integer intervals given as (start, end) tuples; with no intervals it is always free.",
       ["assert is_free([(1, 3)], 3) is False", "assert is_free([(1, 3)], 4) is True", "assert is_free([(1, 3), (5, 8)], 5) is False", "assert is_free([], 0) is True"],
       "def is_free(intervals, t):\n    return not any(s <= t <= e for s, e in intervals)",
       "def is_free(intervals, t):\n    return not any(s < t < e for s, e in intervals)"),
    _t("interval-4", "interval", "sim", "gaps", "`gaps(intervals, lo, hi)` returns the runs of integers from lo to hi (both included) that lie inside none of the closed integer intervals given as (start, end) tuples; each run is a (first, last) tuple, runs are sorted, and the result is empty if everything is covered.",
       ["assert gaps([(2, 3), (6, 6)], 1, 8) == [(1, 1), (4, 5), (7, 8)]", "assert gaps([], 1, 3) == [(1, 3)]", "assert gaps([(1, 5)], 2, 4) == []", "assert gaps([(0, 2), (4, 9)], 1, 5) == [(3, 3)]"],
       "def gaps(intervals, lo, hi):\n    covered = set()\n    for s, e in intervals:\n        covered.update(range(max(s, lo), min(e, hi) + 1))\n    out, start = [], None\n    for n in range(lo, hi + 2):\n        free = n <= hi and n not in covered\n        if free and start is None:\n            start = n\n        elif not free and start is not None:\n            out.append((start, n - 1))\n            start = None\n    return out",
       "def gaps(intervals, lo, hi):\n    covered = set()\n    for s, e in intervals:\n        covered.update(range(max(s, lo), min(e, hi)))\n    out, start = [], None\n    for n in range(lo, hi + 2):\n        free = n <= hi and n not in covered\n        if free and start is None:\n            start = n\n        elif not free and start is not None:\n            out.append((start, n - 1))\n            start = None\n    return out"),
    _t("interval-5", "interval", "sim", "max_overlap", "`max_overlap(intervals)` returns the largest number of the closed integer intervals, given as (start, end) tuples, that all contain one same integer; no intervals gives 0.",
       ["assert max_overlap([(1, 3), (3, 5)]) == 2", "assert max_overlap([(1, 2), (4, 5)]) == 1", "assert max_overlap([(1, 5), (2, 4), (3, 3)]) == 3", "assert max_overlap([]) == 0"],
       "def max_overlap(intervals):\n    if not intervals:\n        return 0\n    lo = min(s for s, e in intervals)\n    hi = max(e for s, e in intervals)\n    return max(sum(1 for s, e in intervals if s <= n <= e) for n in range(lo, hi + 1))",
       "def max_overlap(intervals):\n    if not intervals:\n        return 0\n    lo = min(s for s, e in intervals)\n    hi = max(e for s, e in intervals)\n    return max(sum(1 for s, e in intervals if s <= n < e) for n in range(lo, hi + 1))"),
    # money
    _t("money-1", "money", "exp", "split_bill", "`split_bill(total_cents, n)` shares a whole number of cents between n people (n is at least 1) and returns a list of n integer amounts that add up exactly to total_cents; the amounts differ by at most one cent and the larger amounts come first.",
       ["assert split_bill(100, 3) == [34, 33, 33]", "assert split_bill(10, 5) == [2, 2, 2, 2, 2]", "assert split_bill(1, 3) == [1, 0, 0]", "assert sum(split_bill(997, 4)) == 997"],
       "def split_bill(total_cents, n):\n    q, r = divmod(total_cents, n)\n    return [q + 1] * r + [q] * (n - r)",
       "def split_bill(total_cents, n):\n    return [total_cents // n] * n"),
    _t("money-2", "money", "exp", "round_half_up", "`round_half_up(s, places)` takes a decimal number written as a string and returns it as a string rounded to `places` decimal places, where a value exactly halfway rounds away from zero, so ('2.675', 2) gives '2.68' and ('-2.5', 0) gives '-3'; the result always shows exactly `places` decimals.",
       ["assert round_half_up('2.675', 2) == '2.68'", "assert round_half_up('-2.5', 0) == '-3'", "assert round_half_up('1.005', 2) == '1.01'", "assert round_half_up('3', 2) == '3.00'"],
       "def round_half_up(s, places):\n    from decimal import Decimal, ROUND_HALF_UP\n    q = Decimal(s).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)\n    return format(q, 'f')",
       "def round_half_up(s, places):\n    return str(round(float(s), places))"),
    _t("money-3", "money", "exp", "apply_discount", "`apply_discount(cents, percent)` takes a price in whole cents and a whole-number discount percentage and returns the discounted price in whole cents, rounding a value exactly halfway up.",
       ["assert apply_discount(999, 10) == 899", "assert apply_discount(1005, 50) == 503", "assert apply_discount(100, 0) == 100", "assert apply_discount(250, 100) == 0"],
       "def apply_discount(cents, percent):\n    return (cents * (100 - percent) + 50) // 100",
       "def apply_discount(cents, percent):\n    return int(cents * (1 - percent / 100))"),
    _t("money-4", "money", "sim", "tax_total", "`tax_total(cents, rate_percent)` takes a price in whole cents and a whole-number tax rate in percent and returns the price plus tax in whole cents, where the tax itself is rounded to a whole cent with a value exactly halfway rounded up.",
       ["assert tax_total(1050, 5) == 1103", "assert tax_total(999, 18) == 1179", "assert tax_total(0, 10) == 0", "assert tax_total(1000, 0) == 1000"],
       "def tax_total(cents, rate_percent):\n    return cents + (cents * rate_percent + 50) // 100",
       "def tax_total(cents, rate_percent):\n    return round(cents * (1 + rate_percent / 100))"),
    _t("money-5", "money", "sim", "percent_of", "`percent_of(part, whole)` returns part as a percentage of whole, written as a string with one decimal place and a percent sign, where a value exactly halfway rounds up; when whole is 0 it returns '0.0%'.",
       ["assert percent_of(1, 3) == '33.3%'", "assert percent_of(1, 8) == '12.5%'", "assert percent_of(1, 16) == '6.3%'", "assert percent_of(5, 0) == '0.0%'"],
       "def percent_of(part, whole):\n    from decimal import Decimal, ROUND_HALF_UP\n    if whole == 0:\n        return '0.0%'\n    q = (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)\n    return f'{q}%'",
       "def percent_of(part, whole):\n    return f'{round(part / whole * 100, 1)}%'"),
    # parsing
    _t("parse-1", "parse", "exp", "parse_csv_line", "`parse_csv_line(line)` splits one comma separated line into a list of strings; a field wrapped in double quotes may contain commas, two double quotes inside a quoted field stand for one double quote, and an empty line gives an empty list.",
       ["assert parse_csv_line('a,b,c') == ['a', 'b', 'c']", "assert parse_csv_line('a,\"b,c\",d') == ['a', 'b,c', 'd']", "assert parse_csv_line('x,\"say \"\"hi\"\"\"') == ['x', 'say \"hi\"']", "assert parse_csv_line('') == []"],
       "def parse_csv_line(line):\n    import csv\n    return next(csv.reader([line]), [])",
       "def parse_csv_line(line):\n    return line.split(',')"),
    _t("parse-2", "parse", "exp", "parse_kv", "`parse_kv(s)` turns text like 'a=1;b=2' into a dict of strings: pairs are separated by semicolons, spaces around keys and values are removed, empty pairs are ignored, and only the first equals sign of a pair separates the key from the value, so the value may contain more equals signs.",
       ["assert parse_kv('a=1;b=2') == {'a': '1', 'b': '2'}", "assert parse_kv(' a = x=y ;; b=') == {'a': 'x=y', 'b': ''}", "assert parse_kv('') == {}", "assert parse_kv('k=v;k=w') == {'k': 'w'}"],
       "def parse_kv(s):\n    out = {}\n    for part in s.split(';'):\n        if not part.strip():\n            continue\n        k, _, v = part.partition('=')\n        out[k.strip()] = v.strip()\n    return out",
       "def parse_kv(s):\n    return dict(p.split('=') for p in s.split(';'))"),
    _t("parse-3", "parse", "exp", "balanced", "`balanced(s)` says whether every (, [ and { in the text is closed by the matching bracket in the correct order; all other characters are ignored and an empty text is balanced.",
       ["assert balanced('([]{})') is True", "assert balanced('([)]') is False", "assert balanced('(') is False", "assert balanced('') is True", "assert balanced(')(') is False"],
       "def balanced(s):\n    pairs = {')': '(', ']': '[', '}': '{'}\n    stack = []\n    for c in s:\n        if c in '([{':\n            stack.append(c)\n        elif c in pairs:\n            if not stack or stack.pop() != pairs[c]:\n                return False\n    return not stack",
       "def balanced(s):\n    return s.count('(') == s.count(')') and s.count('[') == s.count(']') and s.count('{') == s.count('}')"),
    _t("parse-4", "parse", "sim", "split_args", "`split_args(s)` splits text on the commas that are not inside parentheses, removes spaces around each part and drops empty parts, so 'f(a,b), c' gives ['f(a,b)', 'c'].",
       ["assert split_args('f(a,b), c') == ['f(a,b)', 'c']", "assert split_args('a,,b') == ['a', 'b']", "assert split_args('') == []", "assert split_args('g(h(1,2),3),4') == ['g(h(1,2),3)', '4']"],
       "def split_args(s):\n    parts, depth, cur = [], 0, ''\n    for c in s:\n        if c == '(':\n            depth += 1\n        elif c == ')':\n            depth -= 1\n        if c == ',' and depth == 0:\n            parts.append(cur)\n            cur = ''\n        else:\n            cur += c\n    parts.append(cur)\n    return [p.strip() for p in parts if p.strip()]",
       "def split_args(s):\n    return [p.strip() for p in s.split(',')]"),
    _t("parse-5", "parse", "sim", "parse_ints", "`parse_ints(text)` returns every whole number found in the text as an int, in order of appearance; a minus sign directly in front of the digits makes the number negative, so 'b-22' contains -22.",
       ["assert parse_ints('a1 b-22 c3') == [1, -22, 3]", "assert parse_ints('no numbers') == []", "assert parse_ints('-5') == [-5]", "assert parse_ints('10 20') == [10, 20]"],
       "def parse_ints(text):\n    import re\n    return [int(x) for x in re.findall(r'-?\\d+', text)]",
       "def parse_ints(text):\n    import re\n    return [int(x) for x in re.findall(r'\\d+', text)]"),
    # boundaries
    _t("boundary-1", "boundary", "exp", "first_ge", "`first_ge(lst, x)` takes a list sorted from smallest to largest and returns the index of the first element that is greater than or equal to x, or the length of the list if there is none.",
       ["assert first_ge([1, 3, 3, 5], 3) == 1", "assert first_ge([1, 2], 5) == 2", "assert first_ge([], 1) == 0", "assert first_ge([4, 6], 1) == 0"],
       "def first_ge(lst, x):\n    from bisect import bisect_left\n    return bisect_left(lst, x)",
       "def first_ge(lst, x):\n    from bisect import bisect_right\n    return bisect_right(lst, x)"),
    _t("boundary-2", "boundary", "exp", "count_in_sorted", "`count_in_sorted(lst, lo, hi)` takes a list sorted from smallest to largest and counts the elements that are at least lo and at most hi, so elements equal to lo or hi count, including repeats.",
       ["assert count_in_sorted([1, 2, 2, 3, 5], 2, 3) == 3", "assert count_in_sorted([1, 2], 5, 9) == 0", "assert count_in_sorted([], 0, 1) == 0", "assert count_in_sorted([2, 2, 2], 2, 2) == 3"],
       "def count_in_sorted(lst, lo, hi):\n    from bisect import bisect_left, bisect_right\n    return bisect_right(lst, hi) - bisect_left(lst, lo)",
       "def count_in_sorted(lst, lo, hi):\n    from bisect import bisect_left\n    return bisect_left(lst, hi) - bisect_left(lst, lo)"),
    _t("boundary-3", "boundary", "exp", "rotate", "`rotate(lst, k)` returns a new list rotated to the right by k places; k may be zero, negative (which rotates to the left) or larger than the length of the list, and an empty list stays empty.",
       ["assert rotate([1, 2, 3, 4], 1) == [4, 1, 2, 3]", "assert rotate([1, 2, 3], 5) == [2, 3, 1]", "assert rotate([1, 2, 3], -1) == [2, 3, 1]", "assert rotate([], 3) == []", "assert rotate([1, 2], 0) == [1, 2]"],
       "def rotate(lst, k):\n    if not lst:\n        return []\n    k %= len(lst)\n    return lst[-k:] + lst[:-k] if k else list(lst)",
       "def rotate(lst, k):\n    return lst[-k:] + lst[:-k]"),
    _t("boundary-4", "boundary", "sim", "chunk", "`chunk(lst, size)` cuts a list into consecutive pieces of the given size (at least 1); the last piece may be shorter, and an empty list gives an empty list.",
       ["assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]", "assert chunk([], 3) == []", "assert chunk([1], 5) == [[1]]", "assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]"],
       "def chunk(lst, size):\n    return [lst[i:i + size] for i in range(0, len(lst), size)]",
       "def chunk(lst, size):\n    return [lst[i:i + size] for i in range(0, len(lst) - size + 1, size)]"),
    _t("boundary-5", "boundary", "sim", "last_le", "`last_le(lst, x)` takes a list sorted from smallest to largest and returns the index of the last element that is less than or equal to x, or -1 if there is none.",
       ["assert last_le([1, 3, 3, 5], 3) == 2", "assert last_le([2], 1) == -1", "assert last_le([], 1) == -1", "assert last_le([1, 2], 9) == 1"],
       "def last_le(lst, x):\n    from bisect import bisect_right\n    return bisect_right(lst, x) - 1",
       "def last_le(lst, x):\n    from bisect import bisect_left\n    return bisect_left(lst, x) - 1"),
    # ---- transfer: pitfalls from several families combined ------------------------------------------------------------------------
    _t("mixed-5", "mixed", "xfer", "merged_count", "`merged_count(intervals)` returns how many intervals remain after merging every pair of closed integer intervals, given as (start, end) tuples, that overlap or share an endpoint; no intervals gives 0.",
       ["assert merged_count([(1, 3), (3, 5), (9, 9)]) == 2", "assert merged_count([]) == 0", "assert merged_count([(1, 2), (4, 5)]) == 2", "assert merged_count([(1, 10), (2, 3)]) == 1"],
       "def merged_count(intervals):\n    out = []\n    for s, e in sorted(intervals):\n        if out and s <= out[-1][1]:\n            out[-1] = (out[-1][0], max(out[-1][1], e))\n        else:\n            out.append((s, e))\n    return len(out)",
       "def merged_count(intervals):\n    out = []\n    for s, e in sorted(intervals):\n        if out and s < out[-1][1]:\n            out[-1] = (out[-1][0], max(out[-1][1], e))\n        else:\n            out.append((s, e))\n    return len(out)"),
    _t("mixed-6", "mixed", "xfer", "average_cents", "`average_cents(cents)` returns the mean of a list of non-negative amounts in whole cents as a whole number of cents, where a value exactly halfway rounds up; an empty list gives 0.",
       ["assert average_cents([2, 3]) == 3", "assert average_cents([]) == 0", "assert average_cents([1, 2, 2, 2]) == 2", "assert average_cents([10]) == 10"],
       "def average_cents(cents):\n    n = len(cents)\n    return (2 * sum(cents) + n) // (2 * n) if n else 0",
       "def average_cents(cents):\n    return round(sum(cents) / len(cents))"),
    _t("mixed-7", "mixed", "xfer", "sum_numbers", "`sum_numbers(text)` returns the sum of all the whole numbers in the text, where a minus sign directly in front of the digits makes a number negative; text with no numbers gives 0.",
       ["assert sum_numbers('a1 b-2 c3') == 2", "assert sum_numbers('none') == 0", "assert sum_numbers('-10 5') == -5", "assert sum_numbers('') == 0"],
       "def sum_numbers(text):\n    import re\n    return sum(int(x) for x in re.findall(r'-?\\d+', text))",
       "def sum_numbers(text):\n    import re\n    return sum(int(x) for x in re.findall(r'\\d+', text))"),
    _t("mixed-8", "mixed", "xfer", "kth_chunk", "`kth_chunk(lst, size, k)` returns the k-th piece (counting from 0) when the list is cut into consecutive pieces of the given size, where the last piece may be shorter, or an empty list if there is no such piece.",
       ["assert kth_chunk([1, 2, 3, 4, 5], 2, 2) == [5]", "assert kth_chunk([1, 2], 2, 1) == []", "assert kth_chunk([], 3, 0) == []", "assert kth_chunk([1, 2, 3], 2, 0) == [1, 2]"],
       "def kth_chunk(lst, size, k):\n    return lst[k * size:(k + 1) * size]",
       "def kth_chunk(lst, size, k):\n    chunks = [lst[i:i + size] for i in range(0, len(lst) - size + 1, size)]\n    return chunks[k]"),
    _t("mixed-9", "mixed", "xfer", "csv_numeric_sum", "`csv_numeric_sum(line)` adds up the fields of one comma separated line that are whole numbers (a minus sign is allowed) and ignores every other field; a field wrapped in double quotes may contain commas and is read without its quotes.",
       ["assert csv_numeric_sum('a,1,\"2\",,x') == 3", "assert csv_numeric_sum('\"1,5\",2') == 2", "assert csv_numeric_sum('') == 0", "assert csv_numeric_sum('-4,6') == 2"],
       "def csv_numeric_sum(line):\n    import csv\n    total = 0\n    for f in next(csv.reader([line]), []):\n        f = f.strip()\n        if f.lstrip('-').isdigit():\n            total += int(f)\n    return total",
       "def csv_numeric_sum(line):\n    return sum(int(f) for f in line.split(',') if f.strip().isdigit())"),
    _t("mixed-10", "mixed", "xfer", "free_slot_count", "`free_slot_count(intervals, lo, hi)` returns how many separate runs of integers from lo to hi (both included) lie inside none of the closed integer intervals given as (start, end) tuples; no free integers gives 0.",
       ["assert free_slot_count([(2, 3), (6, 6)], 1, 8) == 3", "assert free_slot_count([], 1, 3) == 1", "assert free_slot_count([(1, 5)], 2, 4) == 0", "assert free_slot_count([(0, 2), (4, 9)], 1, 5) == 1"],
       "def free_slot_count(intervals, lo, hi):\n    covered = set()\n    for s, e in intervals:\n        covered.update(range(max(s, lo), min(e, hi) + 1))\n    runs, prev_free = 0, False\n    for n in range(lo, hi + 1):\n        free = n not in covered\n        if free and not prev_free:\n            runs += 1\n        prev_free = free\n    return runs",
       "def free_slot_count(intervals, lo, hi):\n    covered = set()\n    for s, e in intervals:\n        covered.update(range(max(s, lo), min(e, hi)))\n    runs, prev_free = 0, False\n    for n in range(lo, hi + 1):\n        free = n not in covered\n        if free and not prev_free:\n            runs += 1\n        prev_free = free\n    return runs"),
    # ======== convention tasks: the spec is natural but leaves out a house convention that only the failing test message reveals ========
    # identifiers: KIND prefix (first three letters, upper case), a hyphen, the number zero-padded to five digits
    _c("ident-1", "ident", "exp", "order_id", "`order_id(n)` returns the identifier of order number n.", ["assert order_id(7) == 'ORD-00007'", "assert order_id(12345) == 'ORD-12345'", "assert order_id(1) == 'ORD-00001'"], "def order_id(n):\n    return f'ORD-{n:05d}'", "def order_id(n):\n    return f'ORD-{n}'"),
    _c("ident-2", "ident", "exp", "invoice_id", "`invoice_id(n)` returns the identifier of invoice number n.", ["assert invoice_id(7) == 'INV-00007'", "assert invoice_id(98765) == 'INV-98765'", "assert invoice_id(42) == 'INV-00042'"], "def invoice_id(n):\n    return f'INV-{n:05d}'", "def invoice_id(n):\n    return f'INV-{n}'"),
    _c("ident-3", "ident", "exp", "customer_id", "`customer_id(n)` returns the identifier of customer number n.", ["assert customer_id(3) == 'CUS-00003'", "assert customer_id(10) == 'CUS-00010'", "assert customer_id(54321) == 'CUS-54321'"], "def customer_id(n):\n    return f'CUS-{n:05d}'", "def customer_id(n):\n    return f'CUS-{n}'"),
    _c("ident-4", "ident", "sim", "shipment_id", "`shipment_id(n)` returns the identifier of shipment number n.", ["assert shipment_id(5) == 'SHI-00005'", "assert shipment_id(123) == 'SHI-00123'", "assert shipment_id(99999) == 'SHI-99999'"], "def shipment_id(n):\n    return f'SHI-{n:05d}'", "def shipment_id(n):\n    return f'SHP-{n}'"),
    _c("ident-5", "ident", "sim", "refund_id", "`refund_id(n)` returns the identifier of refund number n.", ["assert refund_id(4) == 'REF-00004'", "assert refund_id(250) == 'REF-00250'", "assert refund_id(7) == 'REF-00007'"], "def refund_id(n):\n    return f'REF-{n:05d}'", "def refund_id(n):\n    return f'REF-{n}'"),
    _c("ident-6", "ident", "sim", "ticket_id", "`ticket_id(n)` returns the identifier of support ticket number n.", ["assert ticket_id(9) == 'TIC-00009'", "assert ticket_id(31) == 'TIC-00031'", "assert ticket_id(20000) == 'TIC-20000'"], "def ticket_id(n):\n    return f'TIC-{n:05d}'", "def ticket_id(n):\n    return f'TKT-{n}'"),
    # prices: amounts are whole cents, shown with the rupee sign, thousands separators and two decimals; deductions carry a leading minus
    _c("price-1", "price", "exp", "format_price", "`format_price(cents)` shows an amount given in whole cents as text.", ["assert format_price(123456) == '₹1,234.56'", "assert format_price(5) == '₹0.05'", "assert format_price(100000000) == '₹1,000,000.00'"], "def format_price(cents):\n    return f'₹{cents / 100:,.2f}'", "def format_price(cents):\n    return f'{cents / 100:.2f}'"),
    _c("price-2", "price", "exp", "format_refund", "`format_refund(cents)` shows a refund of the given whole cents as text.", ["assert format_refund(2500) == '-₹25.00'", "assert format_refund(123456) == '-₹1,234.56'", "assert format_refund(1) == '-₹0.01'"], "def format_refund(cents):\n    return f'-₹{cents / 100:,.2f}'", "def format_refund(cents):\n    return f'{cents / 100:.2f}'"),
    _c("price-3", "price", "exp", "format_total", "`format_total(cents_list)` shows the sum of a list of amounts in whole cents as text; an empty list gives zero.", ["assert format_total([100000, 50050]) == '₹1,500.50'", "assert format_total([]) == '₹0.00'", "assert format_total([99]) == '₹0.99'"], "def format_total(cents_list):\n    return f'₹{sum(cents_list) / 100:,.2f}'", "def format_total(cents_list):\n    return f'{sum(cents_list) / 100:.2f}'"),
    _c("price-4", "price", "sim", "format_fee", "`format_fee(cents)` shows a fee given in whole cents as text.", ["assert format_fee(250000) == '₹2,500.00'", "assert format_fee(75) == '₹0.75'", "assert format_fee(1234567) == '₹12,345.67'"], "def format_fee(cents):\n    return f'₹{cents / 100:,.2f}'", "def format_fee(cents):\n    return f'₹{cents / 100:.2f}'"),
    _c("price-5", "price", "sim", "format_discount", "`format_discount(cents)` shows a discount of the given whole cents as text.", ["assert format_discount(15000) == '-₹150.00'", "assert format_discount(99) == '-₹0.99'", "assert format_discount(2000000) == '-₹20,000.00'"], "def format_discount(cents):\n    return f'-₹{cents / 100:,.2f}'", "def format_discount(cents):\n    return f'₹{cents / 100:,.2f}'"),
    _c("price-6", "price", "sim", "format_balance", "`format_balance(cents)` shows an account balance, given in whole cents, as text; the balance can be negative.", ["assert format_balance(150000) == '₹1,500.00'", "assert format_balance(-2500) == '-₹25.00'", "assert format_balance(0) == '₹0.00'"], "def format_balance(cents):\n    return f'-₹{-cents / 100:,.2f}' if cents < 0 else f'₹{cents / 100:,.2f}'", "def format_balance(cents):\n    return f'₹{cents / 100:,.2f}'"),
    # dates: DD-Mon-YYYY with a two-digit day, a three-letter English month and a four-digit year
    _c("date-1", "date", "exp", "format_date", "`format_date(year, month, day)` writes a calendar date as text.", ["assert format_date(2026, 3, 5) == '05-Mar-2026'", "assert format_date(1999, 12, 31) == '31-Dec-1999'", "assert format_date(2030, 1, 9) == '09-Jan-2030'"], "def format_date(year, month, day):\n    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']\n    return f'{day:02d}-{months[month - 1]}-{year}'", "def format_date(year, month, day):\n    return f'{year}-{month:02d}-{day:02d}'"),
    _c("date-2", "date", "exp", "format_birthday", "`format_birthday(year, month, day)` writes a person's birth date as text.", ["assert format_birthday(1990, 7, 4) == '04-Jul-1990'", "assert format_birthday(2001, 11, 23) == '23-Nov-2001'", "assert format_birthday(1985, 2, 1) == '01-Feb-1985'"], "def format_birthday(year, month, day):\n    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']\n    return f'{day:02d}-{months[month - 1]}-{year}'", "def format_birthday(year, month, day):\n    return f'{day}/{month}/{year}'"),
    _c("date-3", "date", "exp", "format_expiry", "`format_expiry(year, month, day)` writes the expiry date of a product as text.", ["assert format_expiry(2027, 8, 15) == '15-Aug-2027'", "assert format_expiry(2026, 1, 2) == '02-Jan-2026'", "assert format_expiry(2040, 10, 31) == '31-Oct-2040'"], "def format_expiry(year, month, day):\n    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']\n    return f'{day:02d}-{months[month - 1]}-{year}'", "def format_expiry(year, month, day):\n    return f'{day:02d}.{month:02d}.{year}'"),
    _c("date-4", "date", "sim", "format_deadline", "`format_deadline(year, month, day)` writes a deadline date as text.", ["assert format_deadline(2026, 9, 30) == '30-Sep-2026'", "assert format_deadline(2026, 4, 3) == '03-Apr-2026'", "assert format_deadline(2028, 6, 11) == '11-Jun-2028'"], "def format_deadline(year, month, day):\n    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']\n    return f'{day:02d}-{months[month - 1]}-{year}'", "def format_deadline(year, month, day):\n    return f'{day:02d}-{month:02d}-{year}'"),
    _c("date-5", "date", "sim", "format_start", "`format_start(year, month, day)` writes the start date of a project as text.", ["assert format_start(2026, 5, 1) == '01-May-2026'", "assert format_start(2027, 12, 25) == '25-Dec-2027'", "assert format_start(2026, 2, 14) == '14-Feb-2026'"], "def format_start(year, month, day):\n    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']\n    return f'{day:02d}-{months[month - 1]}-{year}'", "def format_start(year, month, day):\n    return f'{month}/{day}/{year}'"),
    _c("date-6", "date", "sim", "format_range", "`format_range(y1, m1, d1, y2, m2, d2)` writes the period from the first date to the second as text, with the word 'to' between the two dates.", ["assert format_range(2026, 3, 5, 2026, 3, 9) == '05-Mar-2026 to 09-Mar-2026'", "assert format_range(2026, 12, 30, 2027, 1, 2) == '30-Dec-2026 to 02-Jan-2027'", "assert format_range(2030, 6, 1, 2030, 6, 1) == '01-Jun-2030 to 01-Jun-2030'"], "def format_range(y1, m1, d1, y2, m2, d2):\n    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']\n    f = lambda y, m, d: f'{d:02d}-{months[m - 1]}-{y}'\n    return f(y1, m1, d1) + ' to ' + f(y2, m2, d2)", "def format_range(y1, m1, d1, y2, m2, d2):\n    return f'{y1}-{m1:02d}-{d1:02d} to {y2}-{m2:02d}-{d2:02d}'"),
    # errors: bad input raises ValueError whose message is 'invalid <noun>: <the text as given>'
    _c("errors-1", "errors", "exp", "parse_age", '`parse_age(s)` turns text into an age as an int; the age must be a whole number from 0 to 150, and anything else is an error.', ["try:\n    parse_age('abc')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid age: abc', str(e)", "assert parse_age('42') == 42", "try:\n    parse_age('151')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid age: 151', str(e)", "try:\n    parse_age('')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid age: ', str(e)"], "def parse_age(s):\n    try:\n        n = int(s)\n    except ValueError:\n        raise ValueError(f'invalid age: {s}') from None\n    if not 0 <= n <= 150:\n        raise ValueError(f'invalid age: {s}')\n    return n", "def parse_age(s):\n    n = int(s)\n    if not 0 <= n <= 150:\n        raise ValueError('age out of range')\n    return n"),
    _c("errors-2", "errors", "exp", "parse_quantity", '`parse_quantity(s)` turns text into a quantity as an int; the quantity must be a whole number from 1 to 999, and anything else is an error.', ["try:\n    parse_quantity('abc')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid quantity: abc', str(e)", "assert parse_quantity('5') == 5", "try:\n    parse_quantity('1000')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid quantity: 1000', str(e)", "try:\n    parse_quantity('')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid quantity: ', str(e)"], "def parse_quantity(s):\n    try:\n        n = int(s)\n    except ValueError:\n        raise ValueError(f'invalid quantity: {s}') from None\n    if not 1 <= n <= 999:\n        raise ValueError(f'invalid quantity: {s}')\n    return n", "def parse_quantity(s):\n    n = int(s)\n    if not 1 <= n <= 999:\n        raise ValueError('quantity out of range')\n    return n"),
    _c("errors-3", "errors", "exp", "parse_percent", '`parse_percent(s)` turns text into a percent as an int; the percent must be a whole number from 0 to 100, and anything else is an error.', ["try:\n    parse_percent('abc')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid percent: abc', str(e)", "assert parse_percent('50') == 50", "try:\n    parse_percent('101')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid percent: 101', str(e)", "try:\n    parse_percent('')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid percent: ', str(e)"], "def parse_percent(s):\n    try:\n        n = int(s)\n    except ValueError:\n        raise ValueError(f'invalid percent: {s}') from None\n    if not 0 <= n <= 100:\n        raise ValueError(f'invalid percent: {s}')\n    return n", "def parse_percent(s):\n    n = int(s)\n    if not 0 <= n <= 100:\n        raise ValueError('percent out of range')\n    return n"),
    _c("errors-4", "errors", "sim", "parse_port", '`parse_port(s)` turns text into a port as an int; the port must be a whole number from 1 to 65535, and anything else is an error.', ["try:\n    parse_port('abc')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid port: abc', str(e)", "assert parse_port('8080') == 8080", "try:\n    parse_port('65536')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid port: 65536', str(e)", "try:\n    parse_port('')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid port: ', str(e)"], "def parse_port(s):\n    try:\n        n = int(s)\n    except ValueError:\n        raise ValueError(f'invalid port: {s}') from None\n    if not 1 <= n <= 65535:\n        raise ValueError(f'invalid port: {s}')\n    return n", "def parse_port(s):\n    n = int(s)\n    if not 1 <= n <= 65535:\n        raise ValueError('port out of range')\n    return n"),
    _c("errors-5", "errors", "sim", "parse_year", '`parse_year(s)` turns text into a year as an int; the year must be a whole number from 1900 to 2100, and anything else is an error.', ["try:\n    parse_year('abc')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid year: abc', str(e)", "assert parse_year('2026') == 2026", "try:\n    parse_year('2101')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid year: 2101', str(e)", "try:\n    parse_year('')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid year: ', str(e)"], "def parse_year(s):\n    try:\n        n = int(s)\n    except ValueError:\n        raise ValueError(f'invalid year: {s}') from None\n    if not 1900 <= n <= 2100:\n        raise ValueError(f'invalid year: {s}')\n    return n", "def parse_year(s):\n    n = int(s)\n    if not 1900 <= n <= 2100:\n        raise ValueError('year out of range')\n    return n"),
    _c("errors-6", "errors", "sim", "parse_score", '`parse_score(s)` turns text into a score as an int; the score must be a whole number from 0 to 10, and anything else is an error.', ["try:\n    parse_score('abc')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid score: abc', str(e)", "assert parse_score('7') == 7", "try:\n    parse_score('11')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid score: 11', str(e)", "try:\n    parse_score('')\n    assert False, 'did not raise'\nexcept ValueError as e:\n    assert str(e) == 'invalid score: ', str(e)"], "def parse_score(s):\n    try:\n        n = int(s)\n    except ValueError:\n        raise ValueError(f'invalid score: {s}') from None\n    if not 0 <= n <= 10:\n        raise ValueError(f'invalid score: {s}')\n    return n", "def parse_score(s):\n    n = int(s)\n    if not 0 <= n <= 10:\n        raise ValueError('score out of range')\n    return n"),
    _c("mixed-11", "mixed", "xfer", "describe_order", "`describe_order(n, cents)` returns one line about an order: its identifier, then a colon and a space, then its price.", ["assert describe_order(7, 123456) == 'ORD-00007: ₹1,234.56'", "assert describe_order(12, 5) == 'ORD-00012: ₹0.05'", "assert describe_order(99999, 100000000) == 'ORD-99999: ₹1,000,000.00'"], "def describe_order(n, cents):\n    return f'ORD-{n:05d}: ₹{cents / 100:,.2f}'", "def describe_order(n, cents):\n    return f'ORD-{n}: {cents / 100:.2f}'"),
    _c("mixed-12", "mixed", "xfer", "invoice_line", "`invoice_line(n, cents, year, month, day)` returns one line about an invoice: its identifier, a colon and a space, its price, a space, the word 'on', a space, and its date.", ["assert invoice_line(7, 123456, 2026, 3, 5) == 'INV-00007: ₹1,234.56 on 05-Mar-2026'", "assert invoice_line(250, 99, 1999, 12, 31) == 'INV-00250: ₹0.99 on 31-Dec-1999'", "assert invoice_line(1, 100, 2030, 1, 9) == 'INV-00001: ₹1.00 on 09-Jan-2030'"], "def invoice_line(n, cents, year, month, day):\n    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']\n    return f'INV-{n:05d}: ₹{cents / 100:,.2f} on {day:02d}-{months[month - 1]}-{year}'", "def invoice_line(n, cents, year, month, day):\n    return f'INV-{n}: {cents / 100:.2f} on {year}-{month:02d}-{day:02d}'"),
    _c("mixed-13", "mixed", "xfer", "refund_note", "`refund_note(n, cents)` returns one line about a refund: its identifier, then a colon and a space, then the amount refunded.", ["assert refund_note(4, 2500) == 'REF-00004: -₹25.00'", "assert refund_note(88, 123456) == 'REF-00088: -₹1,234.56'", "assert refund_note(12345, 1) == 'REF-12345: -₹0.01'"], "def refund_note(n, cents):\n    return f'REF-{n:05d}: -₹{cents / 100:,.2f}'", "def refund_note(n, cents):\n    return f'REF-{n}: {cents / 100:.2f}'"),
    _c("mixed-14", "mixed", "xfer", "receipt_header", "`receipt_header(n, year, month, day)` returns the heading of a receipt: the receipt identifier, a space, a vertical bar, a space, and the date.", ["assert receipt_header(7, 2026, 3, 5) == 'REC-00007 | 05-Mar-2026'", "assert receipt_header(31, 2027, 12, 25) == 'REC-00031 | 25-Dec-2027'", "assert receipt_header(20000, 2026, 1, 2) == 'REC-20000 | 02-Jan-2026'"], "def receipt_header(n, year, month, day):\n    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']\n    return f'REC-{n:05d} | {day:02d}-{months[month - 1]}-{year}'", "def receipt_header(n, year, month, day):\n    return f'REC-{n} | {year}-{month:02d}-{day:02d}'"),
    _c("mixed-15", "mixed", "xfer", "ticket_label", "`ticket_label(s)` turns the text of a ticket number into the ticket identifier; the number must be a whole number from 1 to 99999, and anything else is an error.", [_raises("ticket_label('abc')", "invalid ticket: abc"), "assert ticket_label('7') == 'TIC-00007'", _raises("ticket_label('0')", "invalid ticket: 0"), "assert ticket_label('12345') == 'TIC-12345'"], "def ticket_label(s):\n    try:\n        n = int(s)\n    except ValueError:\n        raise ValueError(f'invalid ticket: {s}') from None\n    if not 1 <= n <= 99999:\n        raise ValueError(f'invalid ticket: {s}')\n    return f'TIC-{n:05d}'", "def ticket_label(s):\n    n = int(s)\n    if not 1 <= n <= 99999:\n        raise ValueError('ticket number out of range')\n    return f'TIC-{n}'"),
    _c("mixed-16", "mixed", "xfer", "total_line", "`total_line(cents_list)` returns the word 'Total', a colon and a space, then the sum of a list of amounts in whole cents as text; an empty list gives zero.", ["assert total_line([100000, 50050]) == 'Total: ₹1,500.50'", "assert total_line([]) == 'Total: ₹0.00'", "assert total_line([99]) == 'Total: ₹0.99'"], "def total_line(cents_list):\n    return f'Total: ₹{sum(cents_list) / 100:,.2f}'", "def total_line(cents_list):\n    return f'Total: {sum(cents_list) / 100:.2f}'"),
)

BY_ID = {t.id: t for t in TASKS}
FAMILIES = ("empty", "range", "order", "text", "interval", "money", "parse", "boundary", "ident", "price", "date", "errors")




def by_split(split: str, tasks: tuple[Task, ...] | None = None) -> list[Task]:
    return [t for t in (tasks if tasks is not None else TASKS) if t.split == split]


TASK_SETS = ("pitfall", "convention", "all")


def task_set(name: str) -> tuple[Task, ...]:
    if name not in TASK_SETS:
        raise ValueError(f"unknown task set {name!r}; choose from {TASK_SETS}")
    return TASKS if name == "all" else tuple(t for t in TASKS if t.set == name)
