from utils.data_provider import split_dataset, load_movie_categories
import numpy as np
import os
import time
import pandas as pd
import tqdm
import sys
from dataloaders.SlateFormation import SlateFormationDataLoader, SlateFormationTestDataLoader
from torch.utils.data import DataLoader
import json


def slate_formation_future(slate_size, negative_samples_amount, user_interactions, user_movie_matrix,
                           movies_with_no_interactions_with_user):
    slate_movies = []
    response_vector = np.zeros(slate_size, dtype=np.int32)

    positive_samples_amount = slate_size - negative_samples_amount

    # The *or None* will return the whole list when we have 0 positive samples
    all_user_interactions = user_interactions[:-positive_samples_amount or None]

    all_user_interactions_indexes = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id),
                                             all_user_interactions))

    if positive_samples_amount != 0:
        positive_samples = user_interactions[-positive_samples_amount:]

        response_vector[:positive_samples_amount] = 1

        # Convert to indices
        positive_indexes = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id),
                                    positive_samples))

        slate_movies.extend(positive_indexes)

    if negative_samples_amount != 0:
        negative_samples = np.random.choice(movies_with_no_interactions_with_user,
                                            size=negative_samples_amount)

        # Convert to indices
        negative_indexes = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id),
                                    negative_samples))

        slate_movies.extend(negative_indexes)

    response_vector = response_vector.tolist()

    return all_user_interactions_indexes, slate_movies, response_vector


def slate_formation_random(slate_size, negative_samples_amount, user_interactions, user_movie_matrix,
                           movies_with_no_interactions_with_user):
    slate_movies = []
    response_vector = np.zeros(slate_size, dtype=np.int32)

    positive_samples_amount = slate_size - negative_samples_amount

    if positive_samples_amount != 0:
        positive_samples = np.random.choice(np.arange(len(user_interactions)), size=positive_samples_amount, replace=False)
        positive_samples_movies = [user_interactions[positive_sample] for positive_sample in positive_samples]

        response_vector[:positive_samples_amount] = 1

        # Convert to indices
        positive_indexes = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id),
                                    positive_samples_movies))

        slate_movies.extend(positive_indexes)

        all_user_interactions = list(set(user_interactions).difference(set(positive_samples_movies)))

        all_user_interactions_indexes = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id),
                                                 all_user_interactions))
    else:
        # The *or None* will return the whole list when we have 0 positive samples
        all_user_interactions = user_interactions[:-positive_samples_amount or None]

        all_user_interactions_indexes = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id),
                                                 all_user_interactions))

    if negative_samples_amount != 0:
        negative_samples = np.random.choice(movies_with_no_interactions_with_user,
                                            size=negative_samples_amount)

        # Convert to indices
        negative_indexes = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id),
                                    negative_samples))

        slate_movies.extend(negative_indexes)

    response_vector = response_vector.tolist()

    return all_user_interactions_indexes, slate_movies, response_vector


def slate_formation_diverse(slate_size, negative_samples_amount, user_interactions, user_movie_matrix,
                            movies_with_no_interactions_with_user, movies_categories):
    slate_movies = []
    response_vector = np.zeros(slate_size, dtype=np.int32)

    positive_samples_amount = slate_size - negative_samples_amount

    if positive_samples_amount != 0:
        genre_list = []

        for user_interaction in user_interactions:
            genre_list.append(set(np.nonzero(movies_categories[user_movie_matrix.columns.get_loc(user_interaction)])[0]))

        positive_samples_movies = []
        current_genres_in_slate = set()

        for _ in range(positive_samples_amount):
            current_largest_genre_increase = -1
            current_highest_index = -1
            genre_to_add = []

            for idx, genre_movie in enumerate(genre_list):
                current_genre_increase = len(genre_movie.difference(current_genres_in_slate))

                if current_genre_increase > current_largest_genre_increase:
                    current_highest_index = idx
                    current_largest_genre_increase = current_genre_increase
                    genre_to_add = genre_movie

            positive_samples_movies.append(user_interactions[current_highest_index])
            current_genres_in_slate.update(genre_to_add)

        response_vector[:positive_samples_amount] = 1

        # Convert to indices
        positive_indexes = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id),
                                    positive_samples_movies))

        slate_movies.extend(positive_indexes)

        all_user_interactions = list(set(user_interactions).difference(set(positive_samples_movies)))

        all_user_interactions_indexes = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id),
                                                 all_user_interactions))
    else:
        # The *or None* will return the whole list when we have 0 positive samples
        all_user_interactions = user_interactions[:-positive_samples_amount or None]

        all_user_interactions_indexes = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id),
                                                 all_user_interactions))

    if negative_samples_amount != 0:
        negative_samples = np.random.choice(movies_with_no_interactions_with_user,
                                            size=negative_samples_amount)

        # Convert to indices
        negative_indexes = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id),
                                    negative_samples))

        slate_movies.extend(negative_indexes)

    response_vector = response_vector.tolist()

    return all_user_interactions_indexes, slate_movies, response_vector


def generate_slate_formation(row_interactions, user_movie_matrix, slate_size, negative_sampling_for_slates,
                             save_location, movies_categories, dataset_type):
    """
    Return the slates. Each slate has a user_id followed by a slate containing
    *slate_size* movie_ids, *slate_size* response vector (whether the user had an interaction or not) and the user
    interactions. All values are in index form (no ids).
    :param dataset_type:
    :param row_interactions: All the interactions between users and movies. Each value contains user_id, movie_id,
    rating and timestamp.
    :param user_movie_matrix: [user_id, movie_id] Sparse DataFrame matrix where user_id are the rows and movie_id
    are the columns. The value of each [user_id, movie_id] is whether there are an interaction.
    :param slate_size: The size of the slate
    :param negative_sampling_for_slates: This is an array where each element indicates how many negative examples
    per slate.
    :param save_location: Where to save the slates.
    :param movies_categories:
    """
    print("Generating slate formation.....")
    start = time.process_time()

    all_movies_that_can_be_sampled = np.array(user_movie_matrix.columns)

    grouped_users = row_interactions.groupby(['userId'])['movieId'].apply(list)

    all_samples = []

    with tqdm.tqdm(total=len(grouped_users), file=sys.stdout) as pbar:
        for user_id, user_interactions in grouped_users.items():
            if len(user_interactions) <= slate_size:
                pbar.update(1)
                continue

            # Get the possible index of movieIds that we can sample for this user
            movies_with_no_interactions_with_user = np.setxor1d(all_movies_that_can_be_sampled, user_interactions)

            for negative_samples_amount in negative_sampling_for_slates:
                assert negative_samples_amount <= slate_size

                if dataset_type == 'future':
                    all_user_interactions_indexes, slate_movies, response_vector = slate_formation_future(slate_size,
                                                                                                          negative_samples_amount,
                                                                                                          user_interactions,
                                                                                                          user_movie_matrix,
                                                                                                          movies_with_no_interactions_with_user)
                elif dataset_type == 'random':
                    all_user_interactions_indexes, slate_movies, response_vector = slate_formation_random(slate_size,
                                                                                                          negative_samples_amount,
                                                                                                          user_interactions,
                                                                                                          user_movie_matrix,
                                                                                                          movies_with_no_interactions_with_user)
                elif dataset_type == 'diverse':
                    all_user_interactions_indexes, slate_movies, response_vector = slate_formation_diverse(slate_size,
                                                                                                          negative_samples_amount,
                                                                                                          user_interactions,
                                                                                                          user_movie_matrix,
                                                                                                          movies_with_no_interactions_with_user,
                                                                                                          movies_categories)
                else:
                    raise Exception('Dataset type is not valid')

                # Shuffling the negative values
                shuffled = list(zip(slate_movies, response_vector))
                np.random.shuffle(shuffled)
                slate_movies, response_vector = zip(*shuffled)

                slate_genres = np.array(list(map(lambda movie_index: movies_categories[movie_index], slate_movies)))
                unique_genres_in_slate = len(np.unique(np.nonzero(slate_genres)[1]))

                sample = [user_id,
                          '|'.join(str(e) for e in all_user_interactions_indexes),
                          '|'.join(str(e) for e in slate_movies),
                          '|'.join(str(e) for e in response_vector),
                          unique_genres_in_slate]

                all_samples.append(sample)

            pbar.update(1)

    df = pd.DataFrame(all_samples, columns=['User Id', 'User Interactions', 'Slate Movies', 'Response Vector', 'Genres'])
    df.to_csv(save_location, index=False)

    print("Time taken in seconds: ", time.process_time() - start)

    return df


def generate_test_slate_formation(row_interactions, train_row_interactions, user_movie_matrix, save_location):
    print("Generating slate formation.....")
    start = time.process_time()

    grouped_users = row_interactions.groupby(['userId'])['movieId'].apply(list)
    train_grouped_users = train_row_interactions.groupby(['userId'])
    all_samples = []

    with tqdm.tqdm(total=len(grouped_users), file=sys.stdout) as pbar:
        for user_id, user_interactions in grouped_users.items():
            ground_truth = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id), user_interactions))
            training_interaction = train_grouped_users.get_group(user_id)['movieId'].values

            user_condition = list(map(lambda movie_id: user_movie_matrix.columns.get_loc(movie_id), training_interaction))

            sample = [user_id,
                      '|'.join(str(e) for e in ground_truth),
                      '|'.join(str(e) for e in user_condition)]

            all_samples.append(sample)

            pbar.update(1)

    df = pd.DataFrame(all_samples, columns=['User Id', 'Ground Truth', 'User Condition'])
    df.to_csv(save_location, index=False)

    print("Time taken in seconds: ", time.process_time() - start)

    return df


def get_data_loaders(configs, one_hot):
    if not configs['slate_type'] in ['random', 'future', 'diverse']:
        raise Exception('Slate type not found.')

    slate_formation_file_name = 'sf_{}_{}_{}_{}.csv'.format(configs['slate_size'],
                                                         '-'.join(str(e) for e in configs['negative_sampling_for_slates']),
                                                         configs['is_training'], configs['slate_type'])
    slate_formation_file_location = os.path.join(configs['data_location'], slate_formation_file_name)

    slate_formation_file_name = 'sf_{}_{}_{}_{}_test.csv'.format(configs['slate_size'],
                                                              '-'.join(str(e) for e in
                                                                       configs['negative_sampling_for_slates']),
                                                              configs['is_training'], configs['slate_type'])

    slate_formation_test_file_location = os.path.join(configs['data_location'], slate_formation_file_name)

    slate_formation_file_name = 'sf_{}_{}_{}_{}_configs.csv'.format(configs['slate_size'],
                                                                 '-'.join(str(e) for e in
                                                                          configs['negative_sampling_for_slates']),
                                                                 configs['is_training'], configs['slate_type'])
    slate_formation_file_location_configs = os.path.join(configs['data_location'], slate_formation_file_name)

    genre_matrix_location = 'sf_{}_{}_{}_{}_genre_matrix.npy'.format(configs['slate_size'],
                                                                 '-'.join(str(e) for e in
                                                                          configs['negative_sampling_for_slates']),
                                                                 configs['is_training'], configs['slate_type'])

    genre_matrix_location = os.path.join(configs['data_location'], genre_matrix_location)

    title_matrix_location = 'sf_{}_{}_{}_{}_titles.npy'.format(configs['slate_size'],
                                                                 '-'.join(str(e) for e in
                                                                          configs['negative_sampling_for_slates']),
                                                                 configs['is_training'], configs['slate_type'])

    title_matrix_location = os.path.join(configs['data_location'], title_matrix_location)

    # Check if we have the slates for training
    if os.path.isfile(slate_formation_file_location) and os.path.isfile(slate_formation_test_file_location) \
            and os.path.isfile(genre_matrix_location) and os.path.isfile(title_matrix_location):
        slate_formation = pd.read_csv(slate_formation_file_location)
        test_slate_formation = pd.read_csv(slate_formation_test_file_location)

        with open(slate_formation_file_location_configs, 'r') as fp:
            dataset_configs = json.load(fp)

        movies_categories = np.load(genre_matrix_location)
        titles = np.load(title_matrix_location)
    else:
        df_train, df_test, df_train_matrix, df_test_matrix, movies_categories, titles = split_dataset(configs)

        slate_formation = generate_slate_formation(df_train, df_train_matrix, configs['slate_size'],
                                                   configs['negative_sampling_for_slates'],
                                                   slate_formation_file_location,
                                                   movies_categories, configs['slate_type'])

        test_slate_formation = generate_test_slate_formation(df_test, df_train, df_train_matrix,
                                                             slate_formation_test_file_location)
        dataset_configs = {'number_of_users': len(df_train_matrix.index),
                           'number_of_movies': len(df_train_matrix.columns)}

        with open(slate_formation_file_location_configs, 'w') as fp:
            json.dump(dataset_configs, fp)

        np.save(genre_matrix_location, movies_categories)
        np.save(title_matrix_location, titles)

    print(f'Number of users: {dataset_configs["number_of_users"]}, Number of movies: {dataset_configs["number_of_movies"]}')

    train_dataset = SlateFormationDataLoader(slate_formation, dataset_configs['number_of_movies'], one_hot_slates=one_hot)
    train_loader = DataLoader(train_dataset, batch_size=configs['train_batch_size'], shuffle=True, num_workers=4,
                              drop_last=True)

    test_dataset = SlateFormationTestDataLoader(test_slate_formation, dataset_configs['number_of_movies'])
    test_loader = DataLoader(test_dataset, batch_size=configs['test_batch_size'], shuffle=False, num_workers=4,
                             drop_last=False)

    return train_loader, test_loader, dataset_configs, movies_categories, titles
