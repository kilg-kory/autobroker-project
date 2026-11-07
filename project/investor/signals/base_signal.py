
# [open, hight, low, close, +buy signal, +sell signal] 
from util.data_utils import add_column


def signal(data):
    data = add_column(data, 5)
    for i in range(1, len(data)):
        try:
            #Bullish Alpha
            if data[i, 2] < data[i - 5, 2] \
                and data[i, 2] < data[i - 13, 2] \
                    and data[i, 2] < data[i - 21, 2] \
                        and data[i, 3] > data[i - 1, 3] \
                            and data[i, 4] == 0:
                data[i + 1, 4] = 1
            #Bearish Alpha
            if data[i, 1] > data[i - 5, 1] \
                and data[i, 1] > data[i - 13, 1] \
                    and data[i, 1] > data[i - 21, 1] \
                        and data[i, 3] < data[i - 1, 3] \
                            and data[i, 5] == 0:
                data[i + 1, 5] = -1

        except IndexError:
            pass
    return data
