import numpy as np
from torch.utils.data import Dataset


class SlateFormationDataLoader(Dataset):
    def __init__(self, slate_formations, number_of_movies):
        self.slate_formations = slate_formations
        self.number_of_movies = number_of_movies

        self.user_ids = None
        self.slate_vector_matrix = None
        self.response_vector_matrix = None
        self.user_interactions_values = None
        self.longest_user_interaction = 0

        self.convert_to_vector_form()

    def convert_to_vector_form(self):
        self.user_ids = np.stack(self.slate_formations['User Id'].values)

        self.slate_vector_matrix = np.stack(self.slate_formations['Slate Movies'].str.split('|').values)
        self.slate_vector_matrix = self.slate_vector_matrix.astype(np.int32)

        self.response_vector_matrix = np.stack(self.slate_formations['Response Vector'].str.split('|').values)
        self.response_vector_matrix = self.response_vector_matrix.astype(np.int32)

        self.user_interactions_values = self.slate_formations['User Interactions'].str.split('|').values

        # Needed for padding so that every user has the same amount of interactions
        self.longest_user_interaction = len(max(self.user_interactions_values, key=len))

    def __len__(self):
        return len(self.slate_formations)

    def __getitem__(self, idx):
        user_interactions = np.array(self.user_interactions_values[idx]).astype(np.int32)

        # The padding idx is the *self.number_of_movies*
        padded_interactions = np.full(self.longest_user_interaction, self.number_of_movies)
        padded_interactions[0:len(user_interactions)] = user_interactions

        slate_values = np.array(self.slate_vector_matrix[idx])
        slate_one_hot = np.zeros((len(self.slate_vector_matrix[idx]), self.number_of_movies))
        slate_one_hot[np.arange(slate_values.size), slate_values] = 1

        slate_one_hot = slate_one_hot.reshape((len(self.slate_vector_matrix[idx]) * self.number_of_movies,))

        return self.user_ids[idx], padded_interactions, len(user_interactions), slate_one_hot, self.response_vector_matrix[idx]


class SlateFormationTestDataLoader(Dataset):
    def __init__(self, slate_formations, number_of_movies):
        self.slate_formations = slate_formations
        self.number_of_movies = number_of_movies

        self.user_ids = None
        self.user_interactions_values = None
        self.ground_truth = None
        self.longest_user_interaction = None
        self.longest_ground_truth = None

        self.convert_to_vector_form()

    def convert_to_vector_form(self):
        self.user_ids = np.stack(self.slate_formations['User Id'].values)
        self.user_interactions_values = self.slate_formations['User Condition'].str.split('|').values
        self.ground_truth = self.slate_formations['Ground Truth'].str.split('|').values

        # Needed for padding so that every user has the same amount of interactions
        self.longest_user_interaction = len(max(self.user_interactions_values, key=len))

    def __len__(self):
        return self.user_ids.shape[0]

    def __getitem__(self, idx):
        user_interactions = self.user_interactions_values[idx]

        # The padding idx is the *self.number_of_movies*
        padded_interactions = np.full(self.longest_user_interaction, self.number_of_movies)
        padded_interactions[0:len(user_interactions)] = user_interactions

        ground_truth = np.array(self.ground_truth[idx])
        ground_truth_one_hot = np.zeros(self.number_of_movies)

        for mark in ground_truth:
            ground_truth_one_hot[int(mark)] = 1

        return idx, padded_interactions, len(user_interactions), ground_truth_one_hot
