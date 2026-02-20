import json
import os
import pickle
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Embedding, GlobalAveragePooling1D
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from sklearn.preprocessing import LabelEncoder
# =========================
# Configuration
# =========================
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CORE_DIR)

DATA_FILE = os.path.join(CORE_DIR, "intents.json")
MODEL_DIR = os.path.join(CORE_DIR, "model")
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, "chat_model.keras")
TOKENIZER_PATH = os.path.join(MODEL_DIR, "tokenizer.pickle")
LABEL_ENCODER_PATH = os.path.join(MODEL_DIR, "label_encoder.pickle")
# =========================
# Load intents.json
# =========================
with open(DATA_FILE, "r", encoding="utf-8") as f:
    intents = json.load(f)
sentences = []
labels = []
for intent in intents["intents"]:
    for pattern in intent["patterns"]:
        sentences.append(pattern)
        labels.append(intent["tag"])
# =========================
# Encode labels
# =========================
label_encoder = LabelEncoder()
encoded_labels = label_encoder.fit_transform(labels)
num_classes = len(label_encoder.classes_)

# =========================
# Text Vectorization
# =========================
max_tokens = 2000
max_len = 20

tokenizer = Tokenizer(num_words=max_tokens, oov_token="<OOV>")
tokenizer.fit_on_texts(sentences)
sequences = tokenizer.texts_to_sequences(sentences)
X = pad_sequences(sequences, truncating='post', maxlen=max_len)

y = tf.keras.utils.to_categorical(encoded_labels, num_classes=num_classes)
# =========================
# Build Model
# =========================
model = Sequential([
    Embedding(max_tokens, 64),
    GlobalAveragePooling1D(),
    Dense(64, activation="relu"),
    Dense(32, activation="relu"),
    Dense(num_classes, activation="softmax")
])

model.compile(
    optimizer="adam",
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)

# =========================
# Train Model
# =========================
print("🚀 Training Jarvis Brain...")
model.fit(X, y, epochs=200, batch_size=8, verbose=1)

# =========================
# Save Everything
# =========================
model.save(MODEL_PATH)

with open(TOKENIZER_PATH, "wb") as f:
    pickle.dump(tokenizer, f)

with open(LABEL_ENCODER_PATH, "wb") as f:
    pickle.dump(label_encoder, f)

print("✅ Training completed successfully!")
print("🧠 Model saved at:", MODEL_PATH)
print("🧠 Tokenizer saved at:", TOKENIZER_PATH)
print("🧠 Label Encoder saved at:", LABEL_ENCODER_PATH  )
