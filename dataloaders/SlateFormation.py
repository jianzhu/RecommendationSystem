import numpy as np
from torch.utils.data import Dataset


class SlateFormationDataLoader(Dataset):
    def __init__(self, slate_formations, user_movie_matrix):
        self.slate_formations = slate_formations
        self.user_movie_matrix = user_movie_matrix
        self.number_of_movies = len(user_movie_matrix.columns)

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

        # slate_values = np.array()
        # slate_one_hot = np.zeros((len(self.slate_vector_matrix[idx]), self.number_of_movies))
        # slate_one_hot[np.arange(slate_values.size), slate_values] = 1
        #
        # slate_one_hot = slate_one_hot.reshape((len(self.slate_vector_matrix[idx]) * self.number_of_movies,))

        return self.user_ids[idx], padded_interactions, len(user_interactions), self.slate_vector_matrix[idx], self.response_vector_matrix[idx]


class UserConditionedDataLoader(Dataset):
    def __init__(self, row_interactions, user_movie_matrix, train_row_interactions, train_user_movie_matrix, slate_formations):
        self.row_interactions = row_interactions
        self.user_ids = user_movie_matrix.index.to_list()
        self.user_movie_matrix = user_movie_matrix.to_numpy()
        self.slate_formations = slate_formations

        self.train_user_movie_matrix = train_user_movie_matrix
        self.number_of_movies = len(train_user_movie_matrix.columns)

        # Needed for padding so that every user has the same amount of interactions
        self.longest_user_interaction = train_row_interactions.groupby('userId')['movieId'].count()\
                                                              .sort_values(ascending=False).iloc[0]

    def __len__(self):
        return self.user_movie_matrix.shape[0]

    def __getitem__(self, idx):
        user_id = self.user_ids[idx]
        user_interactions = self.slate_formations[self.slate_formations['User Id'] == user_id]['User Interactions'].to_list()
        user_interactions = np.array(user_interactions[0].split('|'))

        # The padding idx is the *self.number_of_movies*
        padded_interactions = np.full(self.longest_user_interaction, self.number_of_movies)
        padded_interactions[0:len(user_interactions)] = user_interactions

        return padded_interactions, len(user_interactions), self.user_movie_matrix[idx]
