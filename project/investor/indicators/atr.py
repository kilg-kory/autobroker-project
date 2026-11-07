from util.data_utils import add_column, delete_column, del_row
from indicators.smoothed_ma import smoothed_ma


def atr(data, lookback, high_column, low_column, close_column, position):
    data = add_column(data, 2)
    for i in range(len(data)):
        try:
            data[i, position] = max(
                data[i, high_column] - data[i, low_column], \
                abs(data[i, high_column] - data[i - 1, close_column]), \
                abs(data[i, low_column] - data[i - 1, close_column]) \
            )
        except ValueError:
            pass
    
    data[0, position] = 0
    data = smoothed_ma(data, 2, lookback, position, position + 1)
    data = delete_column(data, position, 1)
    data = del_row(data, lookback)
    return data
