"""
Configuration file for Action Detection System
"""
import os
import numpy as np

# Data paths
AP_DATA_PATH = "AP_Data"
DATASET_PATH = "dataset/body_language.csv"
PROCESSED_DATA_PATH = "processed_data"

# Model paths
MODEL_PATH = "models"
MODEL_NAME = "enhanced_action_detection_model.h5"
BEST_MODEL_NAME = "best_enhanced_model.h5"

# Data parameters
SEQUENCE_LENGTH = 30
INPUT_SHAPE = (SEQUENCE_LENGTH, 1662)  # 33 pose + 468 face + 21 left hand + 21 right hand landmarks
NUM_CLASSES = 4

# Actions/Classes
ACTIONS = [
    "Confident Expression",
    "Good Posture", 
    "Nervous Expression",
    "Slouching"
]

# Model architecture
LSTM_UNITS = [128, 64, 32]
DENSE_UNITS = [64, 32]

# Training parameters
EPOCHS = 150
BATCH_SIZE = 32
LEARNING_RATE = 0.001
VALIDATION_SPLIT = 0.2
TEST_SPLIT = 0.15

# Feature processing / optimization flags
NORMALIZE_FEATURES = True            # Apply standardization (z-score) across features
USE_SLIDING_WINDOW = True            # Use overlapping windows for CSV frame data
WINDOW_STRIDE = 5                    # Stride for sliding window (frames)
USE_AUGMENTATION = True              # Apply noise augmentation to minority classes
NOISE_STD = 0.005                    # Reduced noise to avoid feature distortion
OVERSAMPLE_MINORITY = True           # Keep oversampling enabled
MAX_AUGMENT_FACTOR = 2               # Lower augmentation factor to reduce class collapse risk

# Detection parameters
DETECTION_THRESHOLD = 0.7
CONFIDENCE_THRESHOLD = 0.6

# Colors for visualization
COLORS = [(245, 117, 16), (117, 245, 16), (16, 117, 245), (245, 16, 117)]

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "enhanced_training.log"

# Data augmentation
USE_DATA_AUGMENTATION = True
AUGMENTATION_FACTOR = 2

# Class balancing
USE_CLASS_WEIGHTS = True
BALANCE_DATASET = True

# Early stopping
EARLY_STOPPING_PATIENCE = 20
REDUCE_LR_PATIENCE = 15
MIN_LR = 0.00001

# Model checkpointing
SAVE_BEST_ONLY = True
MONITOR_METRIC = 'val_categorical_accuracy'

# Ensure colors match number of actions
if len(COLORS) < len(ACTIONS):
    # Add more colors if needed
    additional_colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    COLORS.extend(additional_colors[:len(ACTIONS) - len(COLORS)])

# Create directories
os.makedirs(MODEL_PATH, exist_ok=True)
os.makedirs('logs', exist_ok=True)

ACTIONS = ["Good Posture", "Nervous Expression", "Confident Expression", "Slouching"]
COLORS  = [(0,255,0),(0,200,255),(255,200,0),(255,0,0)]
