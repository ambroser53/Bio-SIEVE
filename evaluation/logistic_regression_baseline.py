import argparse
import pandas as pd
from glob import glob
from sklearn.model_selection import KFold
from sklearn.linear_model import LogisticRegression
from sklearn import metrics
from sklearn.feature_extraction.text import TfidfVectorizer
import nltk
import warnings
from nltk.corpus import stopwords
nltk.download('stopwords')
nltk.download('wordnet')

def warn(*args, **kwargs):
    pass

def preprocess_text(text, stopword_removal=True, lowercase=True):
    text = text.lower() if lowercase else text
    stop_words = set(stopwords.words('english'))
    text = ' '.join([word for word in text.split() if word not in stop_words]) if stopword_removal else text
    text = nltk.WordPunctTokenizer().tokenize(text)
    lemm = nltk.stem.WordNetLemmatizer()
    text = list(map(lambda word: lemm.lemmatize(word), text))
    return text

def main(args):
    warnings.warn = warn
    reviews = glob(f'{args.data_dir}/*.json')
    
    if len(reviews) == 0:
        raise ValueError(f'No reviews found in {args.data_dir}')
    
    label_to_idx = {'Included': 1, 'Excluded': 0}

    kf = KFold(n_splits=args.num_folds, shuffle=True, random_state=0)
    y_hat = []
    labels = []

    for review in reviews:
        review_df = pd.read_json(review)
        review_df['abstract'] = review_df['abstract'].transform(lambda x: preprocess_text(x))
        review_df['label'] = review_df['label'].transform(lambda x: label_to_idx[x])

        review_y_hat = []
        review_labels = []

        for train_index, test_index in kf.split(review_df):
            cv = TfidfVectorizer(tokenizer=lambda x: x, lowercase=False)
            x_train = cv.fit_transform(review_df['abstract'].values[train_index])
            x_test = cv.transform(review_df['abstract'].values[test_index])

            model = LogisticRegression(C=10, random_state=0, max_iter=1000).fit(x_train, review_df['label'].values[train_index])

            review_y_hat.extend(model.predict(x_test))
            review_labels.extend(review_df['label'].values[test_index])
    
        with open(f'{review.split(".")[0]}_lr_results.txt', 'w+') as f:
            f.write(metrics.classification_report(review_labels, review_y_hat))

        y_hat.extend(review_y_hat)
        labels.extend(review_labels)

    with open(f'{args.data_dir}_lr_results.txt', 'w+') as f:
        f.write(metrics.classification_report(labels, y_hat))

    print(metrics.classification_report(labels, y_hat))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_dir', type=str, default='eval_review_subset', help='Directory containing split reviews for kfold training (default: eval_review_subset)')
    parser.add_argument('--num_folds', type=int, default=5, help='Number of folds for kfold training (default: 5)')
    args = parser.parse_args()
    main(args)