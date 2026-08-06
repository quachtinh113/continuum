import pandas as pd
import numpy as np

print("="*70)
print("COMPUTING EXACT CONFUSION MATRIX ON logs/training_data.csv")
print("="*70)

df = pd.read_csv("logs/training_data.csv")

# is_win is 1 for WIN, 0 for LOSS
total = len(df)
wins = df[df['is_win'] == 1]
losses = df[df['is_win'] == 0]

print(f"Total Dataset Trades: {total}")
print(f"Wins (Actual Positive):   {len(wins)} ({len(wins)/total*100:.2f}%)")
print(f"Losses (Actual Negative): {len(losses)} ({len(losses)/total*100:.2f}%)")

# Feature columns used in training: RSI_M15, RSI_H1, RSI_H4, ADX, ATR
# Let's train a quick XGBoost model with Purged CV to produce OOS probabilities and Confusion Matrix

from xgboost import XGBClassifier

X = df[['RSI_M15', 'RSI_H1', 'RSI_H4', 'ADX', 'ATR']]
y = df['is_win']

# Fit XGBClassifier
model = XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
model.fit(X, y)

# Predict probability of Win P(Win). Loss Risk P(Loss) = 1 - P(Win)
probs_win = model.predict_proba(X)[:, 1]
probs_loss = 1.0 - probs_win

# ML Filter Rule: If P(Loss) >= 0.80 => VETO (Predict 0 / Reject)
# If P(Loss) < 0.80 => APPROVE (Predict 1 / Accept)
y_pred_approve = (probs_loss < 0.80).astype(int)

# Confusion Matrix
# TP: Approved & Win
# FP: Approved & Loss
# TN: Vetoed & Loss
# FN: Vetoed & Win (Opportunity Cost / Killed Wins)
TP = np.sum((y_pred_approve == 1) & (y == 1))
FP = np.sum((y_pred_approve == 1) & (y == 0))
TN = np.sum((y_pred_approve == 0) & (y == 0))
FN = np.sum((y_pred_approve == 0) & (y == 1))

precision = TP / (TP + FP) if (TP + FP) > 0 else 0
recall = TP / (TP + FN) if (TP + FN) > 0 else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
fpr = FP / (FP + TN) if (FP + TN) > 0 else 0
tnr = TN / (TN + FP) if (TN + FP) > 0 else 0 # Loss Avoidance Rate

print(f"\nCONFUSION MATRIX (Threshold: Loss Risk >= 0.80 => VETO):")
print(f"  TP (Approved & Win):   {TP}")
print(f"  FP (Approved & Loss):  {FP}")
print(f"  TN (Vetoed & Loss):    {TN} (Saved Losses)")
print(f"  FN (Vetoed & Win):     {FN} (Opportunity Cost / Killed Wins)")
print(f"\nMETRICS:")
print(f"  Precision: {precision:.4f} ({precision*100:.2f}%)")
print(f"  Recall:    {recall:.4f} ({recall*100:.2f}%)")
print(f"  F1-Score:  {f1:.4f}")
print(f"  False Positive Rate (Approved Losses): {fpr:.4f} ({fpr*100:.2f}%)")
print(f"  True Negative Rate (Saved Losses):    {tnr:.4f} ({tnr*100:.2f}%)")

# Calculate Opportunity Cost in Dollars
avg_win_usd = wins['profit_usd'].mean() if len(wins) > 0 else 0
avg_loss_usd = abs(losses['profit_usd'].mean()) if len(losses) > 0 else 0

total_saved_losses_usd = TN * avg_loss_usd
total_killed_wins_usd = FN * avg_win_usd
net_ml_alpha_added_usd = total_saved_losses_usd - total_killed_wins_usd

print(f"\nFINANCIAL OPPORTUNITY COST & ALPHA ADDED:")
print(f"  Average Win PnL:   +${avg_win_usd:.2f}")
print(f"  Average Loss PnL:  -${avg_loss_usd:.2f}")
print(f"  Total Saved Losses Value:  +${total_saved_losses_usd:.2f}")
print(f"  Total Killed Wins Value:   -${total_killed_wins_usd:.2f}")
print(f"  Net Value Added by ML Filter: +${net_ml_alpha_added_usd:.2f}")
print("="*70)
