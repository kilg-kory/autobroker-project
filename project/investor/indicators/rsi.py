


from indicators import smoothed_ma
from util.data_utils import add_column, delete_column, del_row

def rsi(data, lookback, close, position):
    data = add_column(data, 7)
    for i in range(len(data)):
        data[i, position] = data[i, close] - data[i - 1, close]
    for i in range(len(data)):
        if data[i, position] > 0:
            data[i, position + 1] = data[i, position]
        elif data[i, position] < 0:
            data[i, position + 2] = abs(data[i, position])

    data = smoothed_ma(data, 2, lookback, position + 1, position + 3)
    data = smoothed_ma(data, 2, lookback, position + 2, position + 4)

    data[:, position + 5] = data[:, position + 3] / data[:, position + 4]
    data[:, position + 6] = (100 - (100 / (1 + data[:, position + 5])))

    data = delete_column(data, position, 6)
    data = del_row(data, lookback)

    return data