import math
import random


TEST_TICK_SECONDS = 5.0
TEST_TICKS_PER_DAY = 60
_SUNRISE_TICK = 15
_DAY_LENGTH_TICKS = 30

# Deferrable demand model aligned to the provided reference service.
# Each tuple is: ((start_min, start_max), (end_min, end_max), (energy_min, energy_max))
TEST_DEFERRABLE_SPECS = [
    ((0, 0), (TEST_TICKS_PER_DAY - 1, TEST_TICKS_PER_DAY - 1), (50.0, 50.0)),
    ((40, 50), (TEST_TICKS_PER_DAY - 1, TEST_TICKS_PER_DAY - 1), (20.0, 40.0)),
    ((0, 70), (30, TEST_TICKS_PER_DAY - 1), (10.0, 50.0)),
]
TEST_MIN_DEMAND_DURATION = 10


def scheduled_sun_intensity(tick):
    """Sun intensity model aligned with buysellalgorithm/forecast.py.

    Scheduler logic derives day shape from this deterministic profile.
    """
    if tick < _SUNRISE_TICK or tick >= _SUNRISE_TICK + _DAY_LENGTH_TICKS:
        return 0.0
    phase = (tick - _SUNRISE_TICK) * math.pi / _DAY_LENGTH_TICKS
    return float(math.floor(math.sin(phase) * 100.0))


TEST_DEMAND_CYCLE = [
    {"buy_price": 16, "demand": 0.4488824918584866, "sell_price": 33, "tick": 0},
    {"buy_price": 14, "demand": 0.17215213009511632, "sell_price": 28, "tick": 1},
    {"buy_price": 23, "demand": 1.0944590730471448, "sell_price": 46, "tick": 2},
    {"buy_price": 14, "demand": 0.22654427041946834, "sell_price": 29, "tick": 3},
    {"buy_price": 5, "demand": 0.0, "sell_price": 10, "tick": 4},
    {"buy_price": 6, "demand": 0.0, "sell_price": 13, "tick": 5},
    {"buy_price": 14, "demand": 0.16591238261173108, "sell_price": 28, "tick": 6},
    {"buy_price": 15, "demand": 0.27462883342896394, "sell_price": 30, "tick": 7},
    {"buy_price": 10, "demand": 0.0, "sell_price": 21, "tick": 8},
    {"buy_price": 15, "demand": 0.25380374293177044, "sell_price": 30, "tick": 9},
    {"buy_price": 5, "demand": 0.0, "sell_price": 10, "tick": 10},
    {"buy_price": 5, "demand": 0.0, "sell_price": 11, "tick": 11},
    {"buy_price": 48, "demand": 3.196047246797402, "sell_price": 97, "tick": 12},
    {"buy_price": 42, "demand": 2.382300076885616, "sell_price": 85, "tick": 13},
    {"buy_price": 37, "demand": 1.6200742414454221, "sell_price": 75, "tick": 14},
    {"buy_price": 42, "demand": 1.8777779983844822, "sell_price": 84, "tick": 15},
    {"buy_price": 62, "demand": 4.0, "sell_price": 124, "tick": 16},
    {"buy_price": 37, "demand": 1.980647674023776, "sell_price": 75, "tick": 17},
    {"buy_price": 41, "demand": 2.602762488529441, "sell_price": 83, "tick": 18},
    {"buy_price": 50, "demand": 3.750825053556956, "sell_price": 100, "tick": 19},
    {"buy_price": 27, "demand": 1.6868937091944713, "sell_price": 54, "tick": 20},
    {"buy_price": 24, "demand": 1.8632268757832677, "sell_price": 49, "tick": 21},
    {"buy_price": 23, "demand": 2.182351789056225, "sell_price": 47, "tick": 22},
    {"buy_price": 19, "demand": 2.14213566665716, "sell_price": 38, "tick": 23},
    {"buy_price": 5, "demand": 0.6795424328904134, "sell_price": 10, "tick": 24},
    {"buy_price": 5, "demand": 0.8780866095860484, "sell_price": 10, "tick": 25},
    {"buy_price": 15, "demand": 2.581811323205938, "sell_price": 30, "tick": 26},
    {"buy_price": 5, "demand": 0.3704265786576695, "sell_price": 10, "tick": 27},
    {"buy_price": 5, "demand": 1.2987117920436642, "sell_price": 10, "tick": 28},
    {"buy_price": 13, "demand": 2.8188842276876276, "sell_price": 27, "tick": 29},
    {"buy_price": 5, "demand": 1.7306136898882265, "sell_price": 10, "tick": 30},
    {"buy_price": 5, "demand": 0.4776116216842301, "sell_price": 10, "tick": 31},
    {"buy_price": 5, "demand": 0.5820238383587688, "sell_price": 10, "tick": 32},
    {"buy_price": 5, "demand": 1.2143279041994608, "sell_price": 10, "tick": 33},
    {"buy_price": 15, "demand": 2.5725758515694017, "sell_price": 30, "tick": 34},
    {"buy_price": 26, "demand": 3.4553711898259514, "sell_price": 53, "tick": 35},
    {"buy_price": 27, "demand": 3.2587433215475805, "sell_price": 55, "tick": 36},
    {"buy_price": 14, "demand": 1.6702099772772916, "sell_price": 29, "tick": 37},
    {"buy_price": 14, "demand": 1.2532179915587571, "sell_price": 29, "tick": 38},
    {"buy_price": 32, "demand": 2.655043878667433, "sell_price": 65, "tick": 39},
    {"buy_price": 46, "demand": 3.5542398572233296, "sell_price": 92, "tick": 40},
    {"buy_price": 36, "demand": 2.133335954532741, "sell_price": 72, "tick": 41},
    {"buy_price": 59, "demand": 3.919546361137329, "sell_price": 118, "tick": 42},
    {"buy_price": 45, "demand": 2.051304874238165, "sell_price": 91, "tick": 43},
    {"buy_price": 54, "demand": 2.432305514871612, "sell_price": 108, "tick": 44},
    {"buy_price": 65, "demand": 3.036061946427832, "sell_price": 130, "tick": 45},
    {"buy_price": 53, "demand": 1.824330660210716, "sell_price": 106, "tick": 46},
    {"buy_price": 61, "demand": 2.6006833851416524, "sell_price": 122, "tick": 47},
    {"buy_price": 44, "demand": 0.9253889914404476, "sell_price": 88, "tick": 48},
    {"buy_price": 49, "demand": 1.475165003386038, "sell_price": 99, "tick": 49},
    {"buy_price": 57, "demand": 2.2397772368406628, "sell_price": 114, "tick": 50},
    {"buy_price": 56, "demand": 2.396788657424231, "sell_price": 113, "tick": 51},
    {"buy_price": 51, "demand": 2.0516959454648895, "sell_price": 102, "tick": 52},
    {"buy_price": 34, "demand": 0.6164728365369113, "sell_price": 68, "tick": 53},
    {"buy_price": 46, "demand": 2.0025388658289613, "sell_price": 92, "tick": 54},
    {"buy_price": 36, "demand": 1.264641191806168, "sell_price": 72, "tick": 55},
    {"buy_price": 34, "demand": 1.339757117362403, "sell_price": 69, "tick": 56},
    {"buy_price": 40, "demand": 2.161336634173637, "sell_price": 81, "tick": 57},
    {"buy_price": 9, "demand": 0.0, "sell_price": 18, "tick": 58},
    {"buy_price": 35, "demand": 2.0524576803992134, "sell_price": 70, "tick": 59},
]

TEST_SUN_CYCLE = [
    scheduled_sun_intensity(int(item["tick"]))
    for item in TEST_DEMAND_CYCLE
]

TEST_DEMAND_PERIOD_TICKS = len(TEST_DEMAND_CYCLE)


def get_test_deferrables(day):
    """Return deterministic per-day deferrables for test mode replay."""
    random.seed(int(day))
    data = []
    for start_range, end_range, energy_range in TEST_DEFERRABLE_SPECS:
        start = random.randint(int(start_range[0]), int(start_range[1]))
        end = random.randint(int(end_range[0]), int(end_range[1]))
        energy = random.uniform(float(energy_range[0]), float(energy_range[1]))

        if end - start < TEST_MIN_DEMAND_DURATION:
            if start + TEST_MIN_DEMAND_DURATION >= TEST_TICKS_PER_DAY:
                start = end - TEST_MIN_DEMAND_DURATION
            else:
                end = start + TEST_MIN_DEMAND_DURATION

        # Keep window bounded to the replay day tick range.
        start = max(0, min(TEST_TICKS_PER_DAY - 1, int(start)))
        end = max(0, min(TEST_TICKS_PER_DAY - 1, int(end)))

        data.append({"start": start, "end": end, "energy": float(energy)})
    return data
