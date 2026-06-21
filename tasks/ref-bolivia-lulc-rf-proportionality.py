# REFERENCE EXAMPLE - provenance and boundary note
# ---------------------------------------------------------------------------
# Source: Seamus's Winrock Bolivia-External LULC classification workflow
# (Random Forest land-cover classifier on 2018 upland signatures). Provided
# 2026-06-21 as the concrete pattern for the "post-split stratification /
# proportionality checks" requested for the next day-trader model.
#
# This file is a REFERENCE ARTIFACT, not runtime code. It is pasted verbatim
# (paths point at Google Drive; `import os` and `wetland_ha` are referenced but
# not defined in the original snippet - left as-is). The runtime agent does not
# read or execute this. Its purpose is to anchor the spec in TASK_next-model-build.md
# section A: what to adapt, and what to translate, for the trader's binary,
# temporally-split label. See that doc for the translation (random stratified
# split -> temporal split + label-shift audit; multiclass LULC -> binary barrier;
# accuracy/Kappa -> Kappa AND the after-fee money metric).
#
# Pattern elements to carry over:
#   - stratified split preserving class proportions (train_test_split stratify=)
#   - explicit train (and test) class-distribution table
#   - imbalance handling compared head-to-head: natural vs class_weight="balanced"
#     (SMOTE referenced as a third option)
#   - scored by Cohen's Kappa + per-class precision/recall/F1 + confusion matrix
#     + OOB + 10-fold CV accuracy, best chosen by Kappa
#   - feature importance from the chosen model
# ---------------------------------------------------------------------------

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    cohen_kappa_score,
    accuracy_score,
    precision_recall_fscore_support
)
import matplotlib.pyplot as plt
import seaborn as sns
import pickle
print("="*70)
print("Model Evaluation: 2018 Upland Training Data")
print("="*70)
# Load 2018 signatures from Drive
# -----------------------------------------------------------
print("\n1. Loading 2018 signatures from Drive...")
signatures_dir = '/content/drive/MyDrive/Winrock/Bolivia-External/LULC/Outputs/'
samples_signatures_2018 = pickle.load(open(signatures_dir + 'signatures_2018.pkl', 'rb'))
print(f"  ✓ Loaded {len(samples_signatures_2018)} samples")
print(f"  ✓ Classes: {samples_signatures_2018['ipcc_code'].nunique()}")
print(f"  ✓ Features: {samples_signatures_2018.columns.tolist()}")
# Prepare training data
# -----------------------------------------------------------
print("\n2. Preparing training data...")
# Define predictors and response
predictors_2018 = ['BLUE', 'GREEN', 'RED', 'NIR08', 'SWIR16', 'SWIR22', 'NDVI', 'DEM']
response = 'ipcc_code'
# Split into train/test (80/20)
train_2018, test_2018 = train_test_split(
    samples_signatures_2018,
    test_size=0.2,
    random_state=42,
    stratify=samples_signatures_2018[response]
)
X_train = train_2018[predictors_2018]
y_train = train_2018[response]
X_test = test_2018[predictors_2018]
y_test = test_2018[response]
print(f"\nTraining samples: {len(train_2018)}")
print(f"Testing samples: {len(test_2018)}")
print(f"\nClass distribution in training data:")
print(y_train.value_counts().sort_index())
# Model 1: No SMOTE (Natural Distribution)
# -----------------------------------------------------------
print("\n" + "="*70)
print("MODEL 1: Random Forest WITHOUT SMOTE")
print("="*70)
rf_no_smote = RandomForestClassifier(
    n_estimators=500,
    max_features='sqrt',
    random_state=42,
    n_jobs=-1,
    oob_score=True,
    verbose=1
)
print("\nTraining model...")
rf_no_smote.fit(X_train, y_train)
# Cross-validation
print("\nPerforming 10-fold cross-validation...")
cv_scores_no_smote = cross_val_score(
    rf_no_smote, X_train, y_train,
    cv=10, scoring='accuracy', n_jobs=-1
)
print(f"CV Accuracy: {cv_scores_no_smote.mean():.3f} (+/- {cv_scores_no_smote.std() * 2:.3f})")
print(f"OOB Score: {rf_no_smote.oob_score_:.3f}")
# Predictions
y_pred_no_smote = rf_no_smote.predict(X_test)
# Metrics
accuracy_no_smote = accuracy_score(y_test, y_pred_no_smote)
kappa_no_smote = cohen_kappa_score(y_test, y_pred_no_smote)
print("\nClassification Report:")
print(classification_report(y_test, y_pred_no_smote))
print(f"\nCohen's Kappa: {kappa_no_smote:.3f}")
print(f"Accuracy: {accuracy_no_smote:.3f}")
# Model 2: Class-Weighted
# -----------------------------------------------------------
print("\n" + "="*70)
print("MODEL 2: Random Forest WITH CLASS WEIGHTS")
print("="*70)
# Calculate class weights
from sklearn.utils.class_weight import compute_class_weight
class_weights = compute_class_weight(
    class_weight='balanced',
    classes=np.unique(y_train),
    y=y_train
)
class_weight_dict = dict(zip(np.unique(y_train), class_weights))
print("\nComputed class weights:")
for cls, weight in class_weight_dict.items():
    count = (y_train == cls).sum()
    print(f"  Class {cls}: weight={weight:.3f}, samples={count}")
# Train model
rf_weighted = RandomForestClassifier(
    n_estimators=500,
    max_features='sqrt',
    class_weight='balanced',
    random_state=42,
    n_jobs=-1,
    oob_score=True,
    verbose=1
)
print("\nTraining weighted model...")
rf_weighted.fit(X_train, y_train)
# Cross-validation
print("\nPerforming 10-fold cross-validation...")
cv_scores_weighted = cross_val_score(
    rf_weighted, X_train, y_train,
    cv=10, scoring='accuracy', n_jobs=-1
)
print(f"CV Accuracy: {cv_scores_weighted.mean():.3f} (+/- {cv_scores_weighted.std() * 2:.3f})")
print(f"OOB Score: {rf_weighted.oob_score_:.3f}")
# Predictions
y_pred_weighted = rf_weighted.predict(X_test)
# Metrics
accuracy_weighted = accuracy_score(y_test, y_pred_weighted)
kappa_weighted = cohen_kappa_score(y_test, y_pred_weighted)
print("\nClassification Report:")
print(classification_report(y_test, y_pred_weighted))
print(f"\nCohen's Kappa: {kappa_weighted:.3f}")
print(f"Accuracy: {accuracy_weighted:.3f}")
# Summary Comparison
# -----------------------------------------------------------
print("\n" + "="*70)
print("MODEL COMPARISON SUMMARY")
print("="*70)
comparison_df = pd.DataFrame({
    'Model': ['No SMOTE', 'Class Weights'],
    'Accuracy': [accuracy_no_smote, accuracy_weighted],
    'Kappa': [kappa_no_smote, kappa_weighted],
    'CV_Mean': [cv_scores_no_smote.mean(), cv_scores_weighted.mean()],
    'CV_Std': [cv_scores_no_smote.std(), cv_scores_weighted.std()],
    'OOB_Score': [rf_no_smote.oob_score_, rf_weighted.oob_score_]
})
print("\n", comparison_df.to_string(index=False))
# Determine best model
best_idx = comparison_df['Kappa'].idxmax()
best_model_name = comparison_df.loc[best_idx, 'Model']
best_kappa = comparison_df.loc[best_idx, 'Kappa']
print("\n" + "="*70)
print("RECOMMENDATION")
print("="*70)
print(f"\n✓ Best model: {best_model_name} (κ = {best_kappa:.3f})")
if best_model_name == 'No SMOTE':
    best_model = rf_no_smote
    best_predictions = y_pred_no_smote
    print("\n  → Use natural class distribution")
    print("  → No synthetic oversampling needed")
else:
    best_model = rf_weighted
    best_predictions = y_pred_weighted
    print("\n  → Use class weighting")
    print("  → Penalizes minority class misclassification")
# Confusion Matrices
# -----------------------------------------------------------
print("\n3. Creating confusion matrices...")
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
# Model 1
cm_no_smote = confusion_matrix(y_test, y_pred_no_smote)
sns.heatmap(cm_no_smote, annot=True, fmt='d', cmap='Blues',
            xticklabels=np.unique(y_test),
            yticklabels=np.unique(y_test),
            ax=axes[0])
axes[0].set_title(f'No SMOTE\nκ={kappa_no_smote:.3f}, Acc={accuracy_no_smote:.3f}')
axes[0].set_ylabel('True Label')
axes[0].set_xlabel('Predicted Label')
# Model 2
cm_weighted = confusion_matrix(y_test, y_pred_weighted)
sns.heatmap(cm_weighted, annot=True, fmt='d', cmap='Greens',
            xticklabels=np.unique(y_test),
            yticklabels=np.unique(y_test),
            ax=axes[1])
axes[1].set_title(f'Class Weights\nκ={kappa_weighted:.3f}, Acc={accuracy_weighted:.3f}')
axes[1].set_ylabel('True Label')
axes[1].set_xlabel('Predicted Label')
plt.tight_layout()
plt.show()
# Per-Class Performance
# -----------------------------------------------------------
print("\n" + "="*70)
print("PER-CLASS PERFORMANCE")
print("="*70)
precision_no_smote, recall_no_smote, f1_no_smote, _ = precision_recall_fscore_support(
    y_test, y_pred_no_smote, average=None, labels=np.unique(y_test)
)
precision_weighted, recall_weighted, f1_weighted, _ = precision_recall_fscore_support(
    y_test, y_pred_weighted, average=None, labels=np.unique(y_test)
)
class_performance = pd.DataFrame({
    'Class': np.unique(y_test),
    'F1_NoSMOTE': f1_no_smote,
    'F1_Weighted': f1_weighted,
    'Recall_NoSMOTE': recall_no_smote,
    'Recall_Weighted': recall_weighted,
    'Precision_NoSMOTE': precision_no_smote,
    'Precision_Weighted': precision_weighted
})
print("\n", class_performance.to_string(index=False))
# Feature Importance
# -----------------------------------------------------------
print("\n" + "="*70)
print("FEATURE IMPORTANCE (Best Model)")
print("="*70)
importance_df = pd.DataFrame({
    'Feature': predictors_2018,
    'Importance': best_model.feature_importances_
}).sort_values('Importance', ascending=False)
print("\n", importance_df.to_string(index=False))
# Save outputs
# -----------------------------------------------------------
print("\n4. Saving results...")
output_dir = '/content/drive/MyDrive/Winrock/Bolivia-External/LULC/Outputs/'
os.makedirs(output_dir, exist_ok=True)
# Save best model
model_path = output_dir + 'rf_model_2018_best.pkl'
with open(model_path, 'wb') as f:
    pickle.dump(best_model, f)
print(f"  ✓ Best model saved: {model_path}")
# Save comparison results
comparison_df.to_csv(output_dir + 'model_comparison_2018.csv', index=False)
class_performance.to_csv(output_dir + 'per_class_performance_2018.csv', index=False)
importance_df.to_csv(output_dir + 'feature_importance_2018.csv', index=False)
print("  ✓ Results saved to Google Drive")
print("\n" + "="*70)
print("Model Evaluation Complete")
print("="*70)
print(f"\nBest model: {best_model_name}")
print(f"  - Kappa: {best_kappa:.3f}")
print(f"  - Trained on: {len(train_2018)} upland samples")
print(f"  - Wetlands excluded: {wetland_ha:,.0f} ha")
print("\n✓ Ready to apply to all years (2004-2024)")
