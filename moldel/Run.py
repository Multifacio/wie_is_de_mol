from Layers.Moldel import Moldel
from numpy.random import RandomState
from Printers.PieChartPrinter import PieChartPrinter
from Printers.TextSortedPrinter import TextSortedPrinter
import sys

RANDOM_SEED = 949019755
TRAIN_SEASONS = {5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21}
PREDICT_SEASON = 22
LATEST_EPISODE = 6
TRAIN_SEASONS.discard(PREDICT_SEASON)

random_generator = RandomState(RANDOM_SEED)
moldel = Moldel(random_generator)
distribution = moldel.compute_distribution(PREDICT_SEASON, LATEST_EPISODE, TRAIN_SEASONS)
# printer = TextSortedPrinter(0, 2220)
printer = PieChartPrinter()
printer.print(distribution)