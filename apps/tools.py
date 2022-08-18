import pandas as pd

def get_range_string(t_from, t_to):
    str_from = str(t_from.day) + '.'+ str(t_from.month)
    str_to   = str(t_to.day) + '.'+ str(t_to.month)
    
    return str_from + '-' + str_to


def list_of_dates_to_date_ranges(data):
    dg = pd.to_datetime(data)
    ranges = []
    fra = 0
    for ix in range(1, len(dg)):
        to = ix-1
        if((dg[ix] - dg[ix-1])!=pd.Timedelta('1 days')):
            ranges.append(get_range_string(dg[fra], dg[to]))
            fra = ix

    ranges.append(get_range_string(dg[fra], dg[to]))
    
    return ranges