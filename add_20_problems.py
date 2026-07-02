import os
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "online_judge.settings")
django.setup()

from core.models import Problem
from django.contrib.auth.models import User

user = User.objects.filter(is_superuser=True).first()
if not user:
    user = User.objects.first()

problems = [
    # ---- HARD PROBLEMS (Added first so they appear at the bottom) ----
    {
        "title": "Trapping Rain Water",
        "difficulty": "hard",
        "topic": "Arrays",
        "description": "Given `n` non-negative integers representing an elevation map where the width of each bar is `1`, compute how much water it can trap after raining.",
        "constraints": "- `n == height.length`\n- `1 <= n <= 2 * 10^4`\n- `0 <= height[i] <= 10^5`",
        "input_format": "The first line contains an integer `N`, the size of the array.\nThe second line contains `N` space-separated integers representing the elevation map.",
        "output_format": "A single integer representing the total amount of trapped water.",
        "sample_input": "12\n0 1 0 2 1 0 1 3 2 1 2 1",
        "sample_output": "6",
        "test_cases": [
            {"input": "12\n0 1 0 2 1 0 1 3 2 1 2 1", "output": "6"},
            {"input": "6\n4 2 0 3 2 5", "output": "9"},
            {"input": "3\n2 0 2", "output": "2"}
        ]
    },
    {
        "title": "Longest Valid Parentheses",
        "difficulty": "hard",
        "topic": "Strings",
        "description": "Given a string containing just the characters `'('` and `')'`, return the length of the longest valid (well-formed) parentheses substring.",
        "constraints": "- `0 <= s.length <= 3 * 10^4`\n- `s[i]` is `'('`, or `')'`.",
        "input_format": "A single line containing the string `s`.",
        "output_format": "A single integer representing the length of the longest valid parentheses substring.",
        "sample_input": "(()",
        "sample_output": "2",
        "test_cases": [
            {"input": "(()", "output": "2"},
            {"input": ")()())", "output": "4"},
            {"input": "", "output": "0"}
        ]
    },
    {
        "title": "Median of Two Sorted Arrays",
        "difficulty": "hard",
        "topic": "Arrays",
        "description": "Given two sorted arrays `nums1` and `nums2` of size `m` and `n` respectively, return the median of the two sorted arrays.\n\nThe overall run time complexity should be `O(log (m+n))`.",
        "constraints": "- `nums1.length == m`\n- `nums2.length == n`\n- `0 <= m <= 1000`\n- `0 <= n <= 1000`\n- `1 <= m + n <= 2000`\n- `-10^6 <= nums1[i], nums2[i] <= 10^6`",
        "input_format": "The first line contains two integers `M` and `N`.\nThe second line contains `M` space-separated integers for the first array.\nThe third line contains `N` space-separated integers for the second array.",
        "output_format": "A single float representing the median. Format it to exactly 5 decimal places.",
        "sample_input": "2 1\n1 3\n2",
        "sample_output": "2.00000",
        "test_cases": [
            {"input": "2 1\n1 3\n2", "output": "2.00000"},
            {"input": "2 2\n1 2\n3 4", "output": "2.50000"},
            {"input": "0 1\n\n1", "output": "1.00000"}
        ]
    },
    {
        "title": "Regular Expression Matching",
        "difficulty": "hard",
        "topic": "Strings",
        "description": "Given an input string `s` and a pattern `p`, implement regular expression matching with support for `.` and `*` where:\n- `.` Matches any single character.\n- `*` Matches zero or more of the preceding element.\nThe matching should cover the entire input string (not partial).",
        "constraints": "- `1 <= s.length <= 20`\n- `1 <= p.length <= 20`\n- `s` contains only lowercase English letters.",
        "input_format": "The first line contains string `s`.\nThe second line contains string `p`.",
        "output_format": "Print `true` if it matches, `false` otherwise.",
        "sample_input": "aa\na*",
        "sample_output": "true",
        "test_cases": [
            {"input": "aa\na*", "output": "true"},
            {"input": "ab\n.*", "output": "true"},
            {"input": "aab\nc*a*b", "output": "true"}
        ]
    },
    {
        "title": "Merge k Sorted Lists",
        "difficulty": "hard",
        "topic": "Linked List",
        "description": "You are given an array of `k` linked-lists lists, each linked-list is sorted in ascending order.\n\nMerge all the linked-lists into one sorted linked-list and return it. (For simplicity in this problem, we'll represent lists as arrays of numbers).",
        "constraints": "- `k == lists.length`\n- `0 <= k <= 10^4`\n- `0 <= lists[i].length <= 500`",
        "input_format": "The first line contains `K`, the number of lists.\nFor each list, the first line is the size `S`, followed by `S` space-separated integers on the next line.",
        "output_format": "A single line with the merged sorted integers separated by spaces.",
        "sample_input": "3\n3\n1 4 5\n3\n1 3 4\n2\n2 6",
        "sample_output": "1 1 2 3 4 4 5 6",
        "test_cases": [
            {"input": "3\n3\n1 4 5\n3\n1 3 4\n2\n2 6", "output": "1 1 2 3 4 4 5 6"},
            {"input": "1\n0\n", "output": ""},
            {"input": "2\n1\n1\n1\n2", "output": "1 2"}
        ]
    },

    # ---- MEDIUM PROBLEMS (Added next so they appear in the middle) ----
    {
        "title": "Maximum Subarray",
        "difficulty": "medium",
        "topic": "Arrays",
        "description": "Given an integer array `nums`, find the contiguous subarray (containing at least one number) which has the largest sum and return its sum.\n\nA subarray is a contiguous part of an array.",
        "constraints": "- `1 <= nums.length <= 10^5`\n- `-10^4 <= nums[i] <= 10^4`",
        "input_format": "The first line contains an integer `N`, the size of the array.\nThe second line contains `N` space-separated integers representing the elements of the array.",
        "output_format": "A single integer representing the maximum subarray sum.",
        "sample_input": "9\n-2 1 -3 4 -1 2 1 -5 4",
        "sample_output": "6",
        "test_cases": [
            {"input": "9\n-2 1 -3 4 -1 2 1 -5 4", "output": "6"},
            {"input": "1\n1", "output": "1"},
            {"input": "5\n5 4 -1 7 8", "output": "23"}
        ]
    },
    {
        "title": "Merge Intervals",
        "difficulty": "medium",
        "topic": "Arrays",
        "description": "Given an array of intervals where `intervals[i] = [starti, endi]`, merge all overlapping intervals, and return an array of the non-overlapping intervals that cover all the intervals in the input.",
        "constraints": "- `1 <= intervals.length <= 10^4`\n- `intervals[i].length == 2`\n- `0 <= starti <= endi <= 10^4`",
        "input_format": "The first line contains an integer `N`, the number of intervals.\nThe next `N` lines each contain two space-separated integers `start` and `end`.",
        "output_format": "Print the merged intervals, one per line, with space-separated `start` and `end` values.",
        "sample_input": "4\n1 3\n2 6\n8 10\n15 18",
        "sample_output": "1 6\n8 10\n15 18",
        "test_cases": [
            {"input": "4\n1 3\n2 6\n8 10\n15 18", "output": "1 6\n8 10\n15 18"},
            {"input": "2\n1 4\n4 5", "output": "1 5"},
            {"input": "3\n1 4\n0 4\n5 6", "output": "0 4\n5 6"}
        ]
    },
    {
        "title": "Group Anagrams",
        "difficulty": "medium",
        "topic": "Strings",
        "description": "Given an array of strings `strs`, group the anagrams together. You can return the answer in any order.\n\nAn Anagram is a word or phrase formed by rearranging the letters of a different word or phrase, typically using all the original letters exactly once.",
        "constraints": "- `1 <= strs.length <= 10^4`\n- `0 <= strs[i].length <= 100`\n- `strs[i]` consists of lowercase English letters.",
        "input_format": "The first line contains an integer `N`, the number of strings.\nThe second line contains `N` space-separated strings.",
        "output_format": "Print each group of anagrams on a new line, with words space-separated. The order of groups or words does not matter.",
        "sample_input": "6\neat tea tan ate nat bat",
        "sample_output": "eat tea ate\ntan nat\nbat",
        "test_cases": [
            {"input": "6\neat tea tan ate nat bat", "output": "eat tea ate\ntan nat\nbat"},
            {"input": "1\na", "output": "a"},
            {"input": "2\nab ba", "output": "ab ba"}
        ]
    },
    {
        "title": "Longest Substring Without Repeating Characters",
        "difficulty": "medium",
        "topic": "Strings",
        "description": "Given a string `s`, find the length of the longest substring without repeating characters.",
        "constraints": "- `0 <= s.length <= 5 * 10^4`\n- `s` consists of English letters, digits, symbols and spaces.",
        "input_format": "A single line containing the string `s`.",
        "output_format": "A single integer representing the length of the longest substring.",
        "sample_input": "abcabcbb",
        "sample_output": "3",
        "test_cases": [
            {"input": "abcabcbb", "output": "3"},
            {"input": "bbbbb", "output": "1"},
            {"input": "pwwkew", "output": "3"}
        ]
    },
    {
        "title": "Container With Most Water",
        "difficulty": "medium",
        "topic": "Two Pointers",
        "description": "You are given an integer array `height` of length `n`. There are `n` vertical lines drawn such that the two endpoints of the `i`-th line are `(i, 0)` and `(i, height[i])`.\n\nFind two lines that together with the x-axis form a container, such that the container contains the most water.\n\nReturn the maximum amount of water a container can store.",
        "constraints": "- `n == height.length`\n- `2 <= n <= 10^5`\n- `0 <= height[i] <= 10^4`",
        "input_format": "The first line contains an integer `N`.\nThe second line contains `N` space-separated integers representing the heights.",
        "output_format": "A single integer representing the max volume of water.",
        "sample_input": "9\n1 8 6 2 5 4 8 3 7",
        "sample_output": "49",
        "test_cases": [
            {"input": "9\n1 8 6 2 5 4 8 3 7", "output": "49"},
            {"input": "2\n1 1", "output": "1"}
        ]
    },
    {
        "title": "3Sum",
        "difficulty": "medium",
        "topic": "Arrays",
        "description": "Given an integer array nums, return all the triplets `[nums[i], nums[j], nums[k]]` such that `i != j`, `i != k`, and `j != k`, and `nums[i] + nums[j] + nums[k] == 0`.\n\nNotice that the solution set must not contain duplicate triplets.",
        "constraints": "- `3 <= nums.length <= 3000`\n- `-10^5 <= nums[i] <= 10^5`",
        "input_format": "The first line contains `N`.\nThe second line contains `N` space-separated integers.",
        "output_format": "Print each triplet on a new line, space-separated, in any order.",
        "sample_input": "6\n-1 0 1 2 -1 -4",
        "sample_output": "-1 -1 2\n-1 0 1",
        "test_cases": [
            {"input": "6\n-1 0 1 2 -1 -4", "output": "-1 -1 2\n-1 0 1"},
            {"input": "3\n0 1 1", "output": ""},
            {"input": "3\n0 0 0", "output": "0 0 0"}
        ]
    },
    {
        "title": "Number of Islands",
        "difficulty": "medium",
        "topic": "Graphs",
        "description": "Given an `m x n` 2D binary grid `grid` which represents a map of `'1'`s (land) and `'0'`s (water), return the number of islands.\n\nAn island is surrounded by water and is formed by connecting adjacent lands horizontally or vertically.",
        "constraints": "- `m == grid.length`\n- `n == grid[i].length`\n- `1 <= m, n <= 300`",
        "input_format": "The first line contains two integers `m` and `n`.\nThe next `m` lines contain strings of length `n` consisting of `'1'`s and `'0'`s.",
        "output_format": "A single integer for the number of islands.",
        "sample_input": "4 5\n11110\n11010\n11000\n00000",
        "sample_output": "1",
        "test_cases": [
            {"input": "4 5\n11110\n11010\n11000\n00000", "output": "1"},
            {"input": "4 5\n11000\n11000\n00100\n00011", "output": "3"}
        ]
    },

    # ---- EASY PROBLEMS (Added last so they appear at the top) ----
    {
        "title": "Two Sum",
        "difficulty": "easy",
        "topic": "Arrays",
        "description": "Given an array of integers `nums` and an integer `target`, return the indices of the two numbers such that they add up to `target`.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice. You can return the answer in any order.",
        "constraints": "- `2 <= nums.length <= 10^4`\n- `-10^9 <= nums[i] <= 10^9`\n- `-10^9 <= target <= 10^9`\n- Only one valid answer exists.",
        "input_format": "The first line contains an integer `N`, the size of the array. The second line contains `N` space-separated integers. The third line contains the integer `target`.",
        "output_format": "Print two space-separated integers representing the indices (0-indexed) of the two numbers.",
        "sample_input": "4\n2 7 11 15\n9",
        "sample_output": "0 1",
        "test_cases": [
            {"input": "4\n2 7 11 15\n9", "output": "0 1"},
            {"input": "3\n3 2 4\n6", "output": "1 2"},
            {"input": "2\n3 3\n6", "output": "0 1"}
        ]
    },
    {
        "title": "Watermelon",
        "difficulty": "easy",
        "topic": "Math",
        "description": "One hot summer day Pete and his friend Billy decided to buy a watermelon. They chose the biggest and the ripest one, in their opinion. After that the watermelon was weighed, and the scales showed `w` kilos. They rushed home, dying of thirst, and decided to divide the berry, however they faced a hard problem.\n\nPete and Billy are great fans of even numbers, that's why they want to divide the watermelon in such a way that each of the two parts weighs even number of kilos.",
        "constraints": "- `1 <= w <= 100`",
        "input_format": "The first input line contains integer number `w`.",
        "output_format": "Print `YES`, if the boys can divide the watermelon into two parts, each of them weighing even number of kilos; and `NO` in the opposite case.",
        "sample_input": "8",
        "sample_output": "YES",
        "test_cases": [
            {"input": "8", "output": "YES"},
            {"input": "2", "output": "NO"},
            {"input": "3", "output": "NO"},
            {"input": "10", "output": "YES"}
        ]
    },
    {
        "title": "Valid Palindrome",
        "difficulty": "easy",
        "topic": "Strings",
        "description": "A phrase is a palindrome if, after converting all uppercase letters into lowercase letters and removing all non-alphanumeric characters, it reads the same forward and backward. Alphanumeric characters include letters and numbers.\n\nGiven a string `s`, return `true` if it is a palindrome, or `false` otherwise.",
        "constraints": "- `1 <= s.length <= 2 * 10^5`\n- `s` consists only of printable ASCII characters.",
        "input_format": "A single string `s` on a single line.",
        "output_format": "Print `true` if the string is a valid palindrome, otherwise `false`.",
        "sample_input": "A man, a plan, a canal: Panama",
        "sample_output": "true",
        "test_cases": [
            {"input": "A man, a plan, a canal: Panama", "output": "true"},
            {"input": "race a car", "output": "false"},
            {"input": " ", "output": "true"}
        ]
    },
    {
        "title": "Way Too Long Words",
        "difficulty": "easy",
        "topic": "Strings",
        "description": "Sometimes some words like \"localization\" or \"internationalization\" are so long that writing them many times in one text is quite tiresome.\n\nLet's consider a word too long, if its length is strictly more than 10 characters. All too long words should be replaced with a special abbreviation.\n\nThis abbreviation is made like this: we write down the first and the last letter of a word and between them we write the number of letters between the first and the last letters.",
        "constraints": "- `1 <= n <= 100`\n- Each word has a length from 1 to 100 characters.",
        "input_format": "The first line contains an integer `n`.\nEach of the following `n` lines contains one word.",
        "output_format": "Print `n` lines. The `i`-th line should contain the result of replacing of the `i`-th word from the input data.",
        "sample_input": "4\nword\nlocalization\ninternationalization\npneumonoultramicroscopicsilicovolcanoconiosis",
        "sample_output": "word\nl10n\ni18n\np43s",
        "test_cases": [
            {"input": "4\nword\nlocalization\ninternationalization\npneumonoultramicroscopicsilicovolcanoconiosis", "output": "word\nl10n\ni18n\np43s"},
            {"input": "2\nhello\nworld", "output": "hello\nworld"}
        ]
    },
    {
        "title": "Reverse String",
        "difficulty": "easy",
        "topic": "Strings",
        "description": "Write a function that reverses a string. The input string is given as an array of characters `s`.\n\nYou must do this by modifying the input array in-place with `O(1)` extra memory.",
        "constraints": "- `1 <= s.length <= 10^5`",
        "input_format": "A single line containing the string `s`.",
        "output_format": "The reversed string on a single line.",
        "sample_input": "hello",
        "sample_output": "olleh",
        "test_cases": [
            {"input": "hello", "output": "olleh"},
            {"input": "Hannah", "output": "hannaH"}
        ]
    },
    {
        "title": "Fizz Buzz",
        "difficulty": "easy",
        "topic": "Math",
        "description": "Given an integer `n`, return a string array `answer` (1-indexed) where:\n- `answer[i] == \"FizzBuzz\"` if `i` is divisible by 3 and 5.\n- `answer[i] == \"Fizz\"` if `i` is divisible by 3.\n- `answer[i] == \"Buzz\"` if `i` is divisible by 5.\n- `answer[i] == i` (as a string) if none of the above conditions are true.",
        "constraints": "- `1 <= n <= 10^4`",
        "input_format": "A single line containing integer `n`.",
        "output_format": "Print the sequence, each element separated by a space or new line.",
        "sample_input": "3",
        "sample_output": "1\n2\nFizz",
        "test_cases": [
            {"input": "3", "output": "1\n2\nFizz"},
            {"input": "5", "output": "1\n2\nFizz\n4\nBuzz"}
        ]
    },
    {
        "title": "Missing Number",
        "difficulty": "easy",
        "topic": "Math",
        "description": "Given an array `nums` containing `n` distinct numbers in the range `[0, n]`, return the only number in the range that is missing from the array.",
        "constraints": "- `n == nums.length`\n- `1 <= n <= 10^4`\n- `0 <= nums[i] <= n`",
        "input_format": "First line is `N`.\nSecond line is `N` integers.",
        "output_format": "A single integer for the missing number.",
        "sample_input": "3\n3 0 1",
        "sample_output": "2",
        "test_cases": [
            {"input": "3\n3 0 1", "output": "2"},
            {"input": "2\n0 1", "output": "2"},
            {"input": "9\n9 6 4 2 3 5 7 0 1", "output": "8"}
        ]
    },
    {
        "title": "Best Time to Buy and Sell Stock",
        "difficulty": "easy",
        "topic": "Arrays",
        "description": "You are given an array `prices` where `prices[i]` is the price of a given stock on the `i`-th day.\n\nYou want to maximize your profit by choosing a single day to buy one stock and choosing a different day in the future to sell that stock.",
        "constraints": "- `1 <= prices.length <= 10^5`\n- `0 <= prices[i] <= 10^4`",
        "input_format": "First line is `N`.\nSecond line is `N` integers.",
        "output_format": "Max profit.",
        "sample_input": "6\n7 1 5 3 6 4",
        "sample_output": "5",
        "test_cases": [
            {"input": "6\n7 1 5 3 6 4", "output": "5"},
            {"input": "5\n7 6 4 3 1", "output": "0"}
        ]
    }
]

print("Clearing out the previously added problems...")
Problem.objects.all().delete()

print(f"Starting to add {len(problems)} actual coding problems in order (Hard -> Medium -> Easy)...")
count = 0
for data in problems:
    Problem.objects.create(
        title=data["title"],
        difficulty=data["difficulty"],
        description=data["description"],
        constraints=data["constraints"],
        input_format=data["input_format"],
        output_format=data["output_format"],
        sample_input=data["sample_input"],
        sample_output=data["sample_output"],
        tags=data["topic"],
        test_cases_json=json.dumps(data["test_cases"]),
        created_by=user
    )
    count += 1
    print(f"Added: [{data['difficulty'].upper()}] {data['title']}")

print(f"Successfully added {count} authentic coding problems to the database!")
