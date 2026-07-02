import os
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "online_judge.settings")
django.setup()

from core.models import Problem
from django.contrib.auth.models import User

# Get or create a superuser/setter for 'created_by'
user = User.objects.filter(is_superuser=True).first()
if not user:
    user = User.objects.first()

problems = [
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
        "description": "One hot summer day Pete and his friend Billy decided to buy a watermelon. They chose the biggest and the ripest one, in their opinion. After that the watermelon was weighed, and the scales showed `w` kilos. They rushed home, dying of thirst, and decided to divide the berry, however they faced a hard problem.\n\nPete and Billy are great fans of even numbers, that's why they want to divide the watermelon in such a way that each of the two parts weighs even number of kilos, at the same time it is not obligatory that the parts are equal. The boys are extremely tired and want to start their meal as soon as possible, that's why you should help them and find out, if they can divide the watermelon in the way they want. For sure, each of them should get a part of positive weight.",
        "constraints": "- `1 <= w <= 100`",
        "input_format": "The first (and the only) input line contains integer number `w` — the weight of the watermelon bought by the boys.",
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
        "title": "Way Too Long Words",
        "difficulty": "easy",
        "topic": "Strings",
        "description": "Sometimes some words like \"localization\" or \"internationalization\" are so long that writing them many times in one text is quite tiresome.\n\nLet's consider a word too long, if its length is strictly more than 10 characters. All too long words should be replaced with a special abbreviation.\n\nThis abbreviation is made like this: we write down the first and the last letter of a word and between them we write the number of letters between the first and the last letters. That number is in decimal system and doesn't contain any leading zeroes.",
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
    }
]

print("Starting to add 10 actual coding problems...")
count = 0
for data in problems:
    # Delete if exists to prevent duplicates
    Problem.objects.filter(title=data["title"]).delete()
    
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
    print(f"Added: {data['title']}")

print(f"Successfully added {count} authentic coding problems to the database!")
