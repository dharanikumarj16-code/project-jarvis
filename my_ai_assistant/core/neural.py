import os
import numpy as np
import pickle
import logging

# Try to import TensorFlow, but allow the project to run without it.
# Some users run into install issues (OS/CPU/GPU/CUDA, or unsupported Python
# versions). Guarding the import lets the assistant start and degrade
# gracefully when TensorFlow isn't available.
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
TF_AVAILABLE = True
try:
    import tensorflow as tf
    from tensorflow.keras.preprocessing.sequence import pad_sequences
except Exception as _tf_err:
    tf = None
    pad_sequences = None
    TF_AVAILABLE = False
    logging.warning(f"TensorFlow not available: {_tf_err}")
class NeuralBrain:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.lbl_encoder = None
        self.max_len = 20
        self.ready = False
        if not TF_AVAILABLE:
            print("⚠️ TensorFlow is not installed or failed to import. Neural features disabled.")
            self.ready = False
            return

        self._load_brain()

    def _load_brain(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_path, "model")
        
        try:
            model_file = os.path.join(model_path, "chat_model.keras")
            if not os.path.exists(model_file):
                raise FileNotFoundError("Model file not found")

            self.model = tf.keras.models.load_model(model_file)
            
            with open(os.path.join(model_path, "tokenizer.pickle"), 'rb') as handle:
                self.tokenizer = pickle.load(handle)
                
            with open(os.path.join(model_path, "label_encoder.pickle"), 'rb') as handle:
                self.lbl_encoder = pickle.load(handle)
                
            self.ready = True
            print("🧠 Neural Brain loaded successfully.")
        except Exception as e:
            # Avoid printing non-encodable emoji on Windows consoles
            logging.warning(f"Neural Brain not ready: {e}")
            print("Neural Brain not ready:", e)
            print("   (Run 'train_brain.py' to create the neural network)")
            self.ready = False

    def predict(self, text):
        if not self.ready:
            return None, 0.0

        # Preprocess
        sequences = self.tokenizer.texts_to_sequences([text])
        padded = pad_sequences(sequences, truncating='post', maxlen=self.max_len)
        
        # Predict
        result = self.model.predict(padded, verbose=0)
        
        # Get best match
        idx = np.argmax(result)
        confidence = result[0][idx]
        tag = self.lbl_encoder.inverse_transform([idx])[0]
        
        return tag, float(confidence)
