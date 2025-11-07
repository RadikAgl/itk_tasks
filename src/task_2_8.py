nums = [1, 2, 3, 45, 356, 569, 600, 705, 923]


def search(number: id) -> bool:
    left, right = 0, len(nums) - 1

    while left <= right:
        i = (left + right) // 2

        if nums[i] == number:
            return True
        elif nums[i] > number:
            left = i - 1
        else:
            right = i + 1
    return False
