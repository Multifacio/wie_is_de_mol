from Data.ExamData.Dataclasses.DropType import DropType
from Data.ExamData.Exams.All import EXAM_DATA
from Data.Player import Player
from Data.PlayerData import get_is_mol
from Layers.ExamDrop.ExamDropEncoder import ExamDropEncoder, TrainSample
from queue import PriorityQueue
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.feature_selection import VarianceThreshold, SelectFpr, f_classif
from sklearn.preprocessing import KBinsDiscretizer
from typing import List, NamedTuple, Set, Tuple
import numpy as np
import scipy as sc
import sys

FeatureSample = NamedTuple("FeatureSample", [("features", np.array), ("is_mol", bool)])
PredictSample = NamedTuple("PredictSample", [("in_answer", Set[Player]), ("out_answer", Set[Player]),
                                             ("in_features", np.array), ("out_features", np.array), ("weight", float)])
class ExamDropExtractor:
    """ The Exam Drop Extractor deals with obtaining the train data and predict data for the Exam Layer. For this we use
    the following techniques: polynomial transformations, local outlier removal, zero variance removal, ANOVA F filter
    and PCA. Furthermore we resample the data such that every episode has the same likelihood of being picked. """

    BIN_STRATEGY = 'kmeans' # The method used to select the splits between the bins.

    def __init__(self, predict_season: int, predict_episode: int, train_seasons: Set[int], anova_f_significance: float,
                 pca_explain: float, max_splits: int):
        """ Constructor of the Exam Drop Extractor

        Arguments:
            predict_season (int): The season for which we make the prediction.
            predict_episode (int): The latest episode in the predict season that could be used.
            train_seasons (Set[int]): The seasons which are used as train data.
            anova_f_significance (float): Only features with a p-value lower than this value will be selected by the
                ANOVA F filter.
            pca_explain (float): PCA will select the least number of components that at least explain this amount
                of variance in the features.
            max_splits (int): How many additional bins should be used to discretize the features.
        """
        self.__predict_season = predict_season
        self.__predict_episode = predict_episode
        self.__train_seasons = train_seasons
        self.__anova_f_significance = anova_f_significance
        self.__pca_explain = pca_explain
        self.__max_splits = max_splits

    def get_train_data(self) -> Tuple[np.array, np.array, np.array]:
        """ Get the formatted and sampled train data with train weights useable for machine learning algorithms.

        Returns:
            The train input, train output and train weights in this order. The train input is a 2d array where each row
            represents a different train element. The train output is 1d array of labels, such that the ith row of the
            train input corresponds to the ith element of the train output.
        """
        train_data = []
        for season in self.__train_seasons:
            train_data.extend(self.__get_season_data(season, sys.maxsize, True))
        train_input = np.array([ExamDropEncoder.extract_features(sample, sys.maxsize) for sample in train_data])
        train_output = np.array([1.0 if get_is_mol(sample.selected_player) else 0.0 for sample in train_data])

        num_bins = self.get_num_bins(train_input, self.__max_splits)
        self.__discretizer = KBinsDiscretizer(n_bins = num_bins, encode = "onehot-dense",
                                              strategy = ExamDropExtractor.BIN_STRATEGY)
        train_input = self.__discretizer.fit_transform(train_input)
        train_input = self.__add_answered_on_feature(train_data, train_input)
        self.__anova_f_filter = SelectFpr(f_classif, alpha = self.__anova_f_significance)
        train_input = self.__anova_f_filter.fit_transform(train_input, train_output)
        self.__pca = PCA(n_components = self.__pca_explain)
        train_input = self.__pca.fit_transform(train_input)
        return train_input, train_output, self.__get_train_weights(train_data)

    def get_predict_data(self) -> List[PredictSample]:
        """ Get all formatted predict data useable for the machine learning algorithms to do a prediction.

        Returns:
            A list of prediction samples, where a prediction sample consists of a set of players included in the answer
            and not included in the answer. Also a prediction sample consist of the features for the participants
            included in the answer and not included in the answer.
        """
        predict_data = self.__get_season_data(self.__predict_season, self.__predict_episode, False)
        if not predict_data:
            return []

        predict_input = np.array([ExamDropEncoder.extract_features(sample, self.__predict_episode) for sample in predict_data])
        predict_input = self.__discretizer.transform(predict_input)
        predict_input = self.__add_answered_on_feature(predict_data, predict_input)
        predict_input = self.__anova_f_filter.transform(predict_input)
        predict_input = self.__pca.transform(predict_input)

        predict_samples = []
        weights = self.__get_train_weights(predict_data)
        for data, in_features, out_features, weight in zip(predict_data[::2], predict_input[1::2], predict_input[::2], weights):
            in_answer = data.answer
            out_answer = set(data.exam_episode.players).difference(data.answer)
            predict_samples.append(PredictSample(in_answer, out_answer, in_features, out_features, weight))
        return predict_samples

    @staticmethod
    def __get_season_data(season_num: int, max_episode: int, training_data: bool) -> List[TrainSample]:
        """ Get all raw answer data from a season.

        Arguments:
            season_num (int): The season from which we obtain this data.
            max_episode (int): The latest episode which can still be extracted. If this value is sys.maxsize then all
                raw answer data is obtained from this season.
            training_data (bool): True if the data is used as training data and false if the data is used as prediction
                data. The difference is that in case it is used for predictions we use a bool value as selected_player
                and otherwise selected_player is a Player.

        Returns:
            A list of prediction samples, where a prediction sample consists of a set of players included in the answer
            and not included in the answer. Also a prediction sample consist of the features for the participants
            included in the answer and not included in the answer.
        """
        season = EXAM_DATA[season_num]
        drop_players = season.get_drop_mapping(DropType.EXECUTION_DROP, max_episode)
        all_answers = season.get_all_answers(set(drop_players.keys()), max_episode)
        season_data = []
        for answer in all_answers:
            exam_episode = answer.episode
            drop_episodes = drop_players[answer.player]
            drop_episodes = [episode for episode in drop_episodes if exam_episode <= episode]
            if drop_episodes:
                if training_data:
                    for player in exam_episode.players:
                        season_data.append(TrainSample(answer.player, season_num, min(drop_episodes), answer.episode,
                                                       answer.question, answer.answer, player))
                else:
                    for answer_on in [False, True]:
                        season_data.append(TrainSample(answer.player, season_num, min(drop_episodes), answer.episode,
                                                       answer.question, answer.answer, answer_on))
        return season_data

    @staticmethod
    def get_num_bins(train_input: np.array, max_splits: int) -> List[int]:
        """ Get the number of bins for all features. To determine this we use a forward stepwise information gain
        algorithm, which gives the feature with the highest entropy increase an additional bin.

        Arguments:
            train_input (np.array): All non-transformed train input.
            max_splits (int): How many times an additional bin should be added.

        Returns:
            A list of integers, which represent the number of bins for each feature.
        """
        num_bins = [2 for _ in train_input[0]]
        max_bins = [len(set(column)) for column in train_input.T]
        entropies = [ExamDropExtractor.__entropy(np.expand_dims(column, axis = 1), 2) for column in train_input.T]
        options = PriorityQueue()

        for i, data in enumerate(train_input.T):
            if max_bins[i] > 2:
                data = np.expand_dims(data, axis = 1)
                new_entropy = ExamDropExtractor.__entropy(data, 3)
                options.put((-(new_entropy - entropies[i]), i))

        for _ in range(max_splits):
            if options.empty():
                break

            entropy, i = options.get()
            num_bins[i] = num_bins[i] + 1
            entropies[i] = entropies[i] - entropy
            if num_bins[i] != max_bins[i]:
                data = np.expand_dims(train_input[:, i], axis = 1)
                new_entropy = ExamDropExtractor.__entropy(data, num_bins[i] + 1)
                options.put((-(new_entropy - entropies[i]), i))

        return num_bins

    @staticmethod
    def __entropy(data: np.array, bins: int) -> float:
        """ Compute the entropy of a KBinsDiscretizer split using a certain number of bins.

        Arguments:
            data (np.array): A list of all values for a particular feature.
            bins (int): In how many bins the values should be split.

        Returns:
            The entropy of this split.
        """
        discretizer = KBinsDiscretizer(n_bins = bins, encode = "onehot-dense", strategy = ExamDropExtractor.BIN_STRATEGY)
        data = discretizer.fit_transform(data)
        new_entropy = np.sum(data, axis = 0)
        return sc.stats.entropy(new_entropy / np.sum(new_entropy))

    @staticmethod
    def __add_answered_on_feature(samples: List[TrainSample], all_features: np.array) -> np.array:
        """ Translate the features such that answered_on is also included as feature which represents whether the player
        is included in the answer or not. This translation adds a new feature which is 1 if the player is in the answer
        and 0 if not. Also it adds all features multiplied by this answered on features.

        Arguments:
            samples (List[TrainSample]): All raw data corresponding to each row in all_features. This data is used
                to check if a player was included in the answer or not.
            all_features (np.array): All feature values so far.

        Returns:
            All new feature values translated by adding the answered_on feature to it.
        """
        new_features = []
        for sample, features in zip(samples, all_features):
            if isinstance(sample.selected_player, bool):
                answered_on = 1.0 if sample.selected_player else 0.0
            else:
                answered_on = 1.0 if sample.selected_player in sample.answer else 0.0
            features = np.append(features, answered_on * features)
            features = np.append(features, [answered_on])
            new_features.append(features)
        return np.array(new_features)

    @staticmethod
    def __get_train_weights(train_data: List[TrainSample]) -> np.array:
        """ Get the weight for the training data, which is 1 / num_answers where num_answers is the number of answers
        given by that player in that episode.

        Arguments:
            train_data (List[TrainSample]): All raw train data from which it is extracted to which episode an answer
                belongs.

        Returns:
            An 1d array of weights which pairwise corresponds to the train_data (and therefore pairwise corresponds
            with each row in the train input).
        """
        train_weights = []
        for sample in train_data:
            num_answers = sample.exam_episode.get_all_answers({sample.player}, sys.maxsize)
            train_weights.append(1 / len(num_answers))
        return np.array(train_weights)