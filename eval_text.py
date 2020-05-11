import numpy as np
import h5py, os, sys, glob, argparse
import re, nltk
from gensim.models import KeyedVectors
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import accuracy_score, precision_score, f1_score, recall_score
from sklearn.cluster import KMeans
nltk.download("popular", download_dir="/tf/nltk")
nltk.data.path.append("/tf/nltk");
stop_words = nltk.corpus.stopwords.words()
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2' 
import tensorflow as tf
gpus = tf.config.experimental.list_physical_devices('GPU')
for gpu in gpus:
    tf.config.experimental.set_memory_growth(gpu, True)

# Function to get the id of each image
def get_ordered_uniques(ids, labs):
    uniques = []
    labels = []
    prev = 0
    for i in range(ids.size):
        if ids[i]!=prev: uniques.append(ids[i]); labels.append(labs[i])
        prev = ids[i]
    return uniques, np.array(labels)

def get_reports_names(reports_paths, id_unique):
    paths = []
    for idx in id_unique:
        valid_idx = "-".join(idx.split("-")[:3])
        for path in reports_paths:
            if valid_idx in path:
                paths.append(path)
                break
    return paths

def load_corpus(paths):
    corpus = []
    for path in paths:
        with open(path, "r") as f:
            corpus.append(f.read())
    return corpus

def preprocessing(doc):
    res = re.sub(r"(\d)\s*.\s*(\d)", r"\1.\2", doc)
    res = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", res)
    res = re.sub(r"(\d)\s*[x|X]\s*(\d)", r"\1x\2", res)
    res = re.sub(r"\n+|[;!\"$&/()=?¿\-\|!\"@#~€¬:,'¡*¢^`]", " ", res)
    res = re.sub(r"([a-zA-Z])(\s*)\.", r"\1\2", res)
    res = re.sub(r"([a-zA-Z])\1{2,}", " ", res)
    res = re.sub(r"\s+", " ", res)
    res = re.sub(r"\s\.\s", " ", res)
    res = re.sub(r"(\w)\.\s", r"\1 ", res)
    res = re.sub(r"(\w)\.\s", r"\1 ", res)
    res = re.sub(r"\s[a-zA-Z]\s", r" ", res)
    res = " ".join([token for token in res.split(" ") if token not in stop_words and len(token)<10])
    res = res.lower()
    return res

def create_model(units, act, dim):
    model = tf.keras.models.Sequential()
    # Primer capa intermedia con dropout
    model.add(tf.keras.layers.Dense(units, activation=act, input_shape=(dim, )))
    model.add(tf.keras.layers.Dropout(0.2))
    # Segunda capa intermedia con dropout
    model.add(tf.keras.layers.Dense(units, activation=act))
    model.add(tf.keras.layers.Dropout(0.2))
    # Capa de salida
    model.add(tf.keras.layers.Dense(5, activation="softmax"))
    # Compilamos el modelo
    model.compile(loss="categorical_crossentropy", optimizer=tf.optimizers.Adam(lr=1e-4),
                  metrics=["accuracy"])
    return model

def train_ngram(train_corpus, y_train, val_corpus, y_val, test_corpus, y_test):
    names = ["ngram", "Accuracy", "Precision", "F1", "Recall"]
    print("".join([f'{val:20}' for val in names]))
    for ngram in range(1, 8):
        cv = CountVectorizer(max_df=0.5, min_df=0.01, ngram_range=(1, ngram))
        cv.fit(full_corpus)

        X_train = cv.transform(train_corpus).toarray()
        X_val = cv.transform(val_corpus).toarray()
        X_train2 = np.concatenate([X_train, X_val], axis=0)
        y_train2 = np.concatenate([y_train, y_val])
        X_test = cv.transform(test_corpus).toarray()

        Y_train2 = tf.keras.utils.to_categorical(y_train2)
        Y_train = tf.keras.utils.to_categorical(y_train)
        Y_val = tf.keras.utils.to_categorical(y_val)
        Y_test = tf.keras.utils.to_categorical(y_test)
        acc = []; prec = []; f1 = []; rec = []
        for i in range(10):
            model = create_model(32, "relu", X_train.shape[1])
            cb = tf.keras.callbacks.ModelCheckpoint("bow_ann.h5")
            model.fit(X_train, Y_train, validation_data=(X_val, Y_val), callbacks=[cb], epochs=100,
                      batch_size=16, verbose=0)
            model.load_weights("bow_ann.h5")

            preds = model.predict(X_test)
            y_pred = np.argmax(preds, axis=1)
            acc.append(accuracy_score(y_test, y_pred))
            prec.append(precision_score(y_test, y_pred, average="weighted"))
            f1.append(f1_score(y_test, y_pred, average="weighted"))
            rec.append(recall_score(y_test, y_pred, average="weighted"))
        print(f'{ngram:<20}'+"".join(map(lambda i:f'{i:20}',[f'{avg:.4f}'+u"\u00B1"+f'{std:.4f}' for avg, std in zip([np.mean(acc), np.mean(prec), np.mean(f1), np.mean(rec)], [np.std(acc), np.std(prec), np.std(f1), np.std(rec)])])))  
    
def train_tfidf(train_corpus, y_train, val_corpus, y_val, test_corpus, y_test):
    names = ["ngram", "Accuracy", "Precision", "F1", "Recall"]
    print("".join([f'{val:20}' for val in names]))
    for ngram in range(1, 8):
        cv = TfidfVectorizer(max_df=0.5, min_df=0.01, ngram_range=(1, ngram), sublinear_tf=True)
        cv.fit(full_corpus)

        X_train = cv.transform(train_corpus).toarray()
        X_val = cv.transform(val_corpus).toarray()
        X_train2 = np.concatenate([X_train, X_val], axis=0)
        y_train2 = np.concatenate([y_train, y_val])
        X_test = cv.transform(test_corpus).toarray()

        Y_train2 = tf.keras.utils.to_categorical(y_train2)
        Y_train = tf.keras.utils.to_categorical(y_train)
        Y_val = tf.keras.utils.to_categorical(y_val)
        Y_test = tf.keras.utils.to_categorical(y_test)
        acc = []; prec = []; f1 = []; rec = []
        for i in range(10):
            model = create_model(32, "relu", X_train.shape[1])
            cb = tf.keras.callbacks.ModelCheckpoint("tfidf_ann.h5")
            model.fit(X_train, Y_train, validation_data=(X_val, Y_val), callbacks=[cb], epochs=100,
                      batch_size=16, verbose=0)
            model.load_weights("tfidf_ann.h5")

            preds = model.predict(X_test)
            y_pred = np.argmax(preds, axis=1)
            acc.append(accuracy_score(y_test, y_pred))
            prec.append(precision_score(y_test, y_pred, average="weighted"))
            f1.append(f1_score(y_test, y_pred, average="weighted"))
            rec.append(recall_score(y_test, y_pred, average="weighted"))
        print(f'{ngram:<20}'+"".join(map(lambda i:f'{i:20}',[f'{avg:.4f}'+u"\u00B1"+f'{std:.4f}' for avg, std in zip([np.mean(acc), np.mean(prec), np.mean(f1), np.mean(rec)], [np.std(acc), np.std(prec), np.std(f1), np.std(rec)])])))  

def get_masks(corpus, kmeans_model):
    masks = []
    for doc in corpus:
        doc_repr = []
        for word in doc:
            try:
                doc_repr.append(model[word].reshape(1, -1))
            except:
                pass
        doc_repr = np.concatenate(doc_repr, axis=0)
        masks.append(" ".join(map(lambda i: f"cluster{i}", kmeans_model.predict(doc_repr))))
    return masks

if __name__=="__main__":
    # Get patient id for each document
    with h5py.File("/tf/TCGA/images.h5", "r") as df:
        train_id = df["id_train"][:]
        y_train_full = df["y_train"][:]
        val_id = df["id_val"][:]
        y_val_full = df["y_val"][:]
        test_id = df["id_test"][:]
        y_test_full = df["y_test"][:]

    train_id_unique, y_train = get_ordered_uniques(train_id, y_train_full)
    val_id_unique, y_val = get_ordered_uniques(val_id, y_val_full)
    test_id_unique, y_test = get_ordered_uniques(test_id, y_test_full)
    reports_paths = glob.glob("/tf/TCGA/reports_txt/*")
    
    train_paths = get_reports_names(reports_paths, train_id_unique)
    val_paths = get_reports_names(reports_paths, val_id_unique)
    test_paths = get_reports_names(reports_paths, test_id_unique)
    
    train_corpus = load_corpus(train_paths)
    val_corpus = load_corpus(val_paths)
    test_corpus = load_corpus(test_paths)
    
    train_corpus = list(map(preprocessing, train_corpus))
    val_corpus = list(map(preprocessing, val_corpus))
    test_corpus = list(map(preprocessing, test_corpus))
    
    full_corpus = []
    for corpus in [train_corpus, val_corpus, test_corpus]:
        full_corpus.extend(corpus)
        
    parser = argparse.ArgumentParser(description='Train and evaluate a specified text representation.')
    parser.add_argument("--repr", type=str, help="Representation to evaluate", default="ngram")
    args = parser.parse_args()
    os.system("clear")
    
    if args.repr=="ngram":
        train_ngram(train_corpus, y_train, val_corpus, y_val, test_corpus, y_test)
    elif args.repr=="tfidf":
        train_tfidf(train_corpus, y_train, val_corpus, y_val, test_corpus, y_test)
    elif args.repr=="bioword2vec":
        # Load BioWord2Vec Model
        model = KeyedVectors.load_word2vec_format("/tf/TCGA/embedding_models/bioword2vec.bin", binary=True)
        # Get vocabulary
        all_words = " "
        for corpus in [train_corpus, val_corpus, test_corpus]:
            all_words = all_words.join(corpus)
        vocab = [i for i in list(set(all_words.split(" "))) if len(i)!=0]
        # Get vocabulary representations
        reprs = []
        excluded = []
        for word in vocab:
            try:
                reprs.append(model.wv[word].reshape(1, -1))
            except:
                excluded.append(word)
        reprs = np.concatenate(reprs, axis=0)
        # train KMeans model
        kmeans_model = KMeans(500).fit(reprs)
        # Get all masked tokens
        train_masks = get_masks(train_corpus, kmeans_model)
        val_masks = get_masks(val_corpus, kmeans_model)
        test_masks = get_masks(test_corpus, kmeans_model)
        train_ngram(train_masks, y_train, val_masks, y_val, test_masks, y_test)
    elif args.repr=="bioword2vec_tfidf":
        # Load BioWord2Vec Model
        model = KeyedVectors.load_word2vec_format("/tf/TCGA/embedding_models/bioword2vec.bin", binary=True)
        # Get vocabulary
        all_words = " "
        for corpus in [train_corpus, val_corpus, test_corpus]:
            all_words = all_words.join(corpus)
        vocab = [i for i in list(set(all_words.split(" "))) if len(i)!=0]
        # Get vocabulary representations
        reprs = []
        excluded = []
        for word in vocab:
            try:
                reprs.append(model.wv[word].reshape(1, -1))
            except:
                excluded.append(word)
        reprs = np.concatenate(reprs, axis=0)
        # train KMeans model
        kmeans_model = KMeans(500).fit(reprs)
        # Get all masked tokens
        train_masks = get_masks(train_corpus, kmeans_model)
        val_masks = get_masks(val_corpus, kmeans_model)
        test_masks = get_masks(test_corpus, kmeans_model)
        train_tfidf(train_masks, y_train, val_masks, y_val, test_masks, y_test)