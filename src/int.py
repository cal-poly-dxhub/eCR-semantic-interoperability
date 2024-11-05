from typing import Any

money: list[Any] = [
    [0.01, "penny"],
    [0.05, "nickel"],
    [0.10, "dime"],
    [0.25, "quarter"],
    [0.50, "fifty"],
    [1, "one"],
    [2, "two"],
    [5, "five"],
    [10, "ten"],
]
lm = len(money) - 1


goal = 6.36
comb: list[Any] = []
sum = 0

while sum < goal:
    print("sum ", end="")
    print(sum)
    print(" comb ", end="")
    print(comb)
    for i in range(len(money)):
        if sum + money[lm - i][0] <= goal:
            sum += money[lm - i][0]
            comb.append(money[lm - i])
            sum = round(sum, 2)
            break
    if sum == goal:
        print(comb)
