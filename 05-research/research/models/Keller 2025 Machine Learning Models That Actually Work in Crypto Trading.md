

## Machine Learning Models
That Actually Work in
## Crypto Trading
Adrian KellerFollow
18 min read·Dec 13, 2025
## 1264
Why 90% of ML trading models fail in production — and
what the successful 10% do differently
## The $2 Million Lesson
In 2018, fresh from completing my Ph.D. in Financial
Engineering, I was convinced I’d solved crypto trading
with machine learning.
My deep learning model had achieved 73% accuracy on
historical data. The backtest showed 340% annual
returns. The Sharpe ratio was an impressive 2.8. Every
metric screamed success.
Welcome OfferAccess to everything. Now up to 30% off.
Upgrade now
SearchGet appWrite
Find writers and
publications to follow.
See suggestions
## Home
## Library
## Profile
## Stories
## Stats
## Following
## Pratyush Tripathy

metric screamed success.
I deployed it with $2 million in capital.
Six weeks later, I was down 18%.
The model that looked brilliant on historical data was
making catastrophic decisions in live markets. It was
buying tops and selling bottoms. It was reacting to noise
as if it were signal. It was, quite simply, failing
spectacularly.
That expensive failure taught me more about machine
learning in trading than my entire Ph.D. program. Over
the past seven years, I’ve rebuilt our systems from the
ground up, testing dozens of ML approaches and
discarding most of them.
Today, our fund runs profitable ML-driven strategies.
But the models that work look nothing like what
academic papers suggest or what crypto Twitter
promotes.
This article shares what actually works — and more
importantly, why most approaches fail.
Why Most ML Trading Models Fail
Before discussing solutions, let’s understand the failure
modes. Here are the five reasons I’ve seen ML trading
models collapse in production:
Failure Mode 1: Overfitting to Noise
The problem
: Crypto markets have limited historical
data. Bitcoin has only existed since 2009. Most altcoins
have even shorter histories. ML models, especially deep
learning, need massive datasets.
What happens
: Models memorize historical noise rather
than learning genuine patterns. They fit perfectly to the
past but have zero predictive power for the future.

past but have zero predictive power for the future.
Real example from our research
## :
The lesson
: Parameter count must be proportional to
data quantity. For crypto, simpler is almost always
better.
Failure Mode 2: Non-Stationarity Ignored
The problem
: Financial markets are non-stationary —
their statistical properties change over time. A pattern
that worked in 2017’s bull market fails in 2022’s bear
market.
What happens
: Models trained on one market regime
perform poorly when the regime shifts. They’re fighting
the last war.
## Example
## :
Bull market 2020–2021: “Buy the dip” strategies
worked brilliantly
Bear market 2022: Same strategy resulted in catching
falling knives
A model trained primarily on bull market data was
useless in the bear
# Our early mistake: Complex model on limited data
model = Sequential([
LSTM(128, return_sequences=True),
## Dropout(0.3),
LSTM(64, return_sequences=True),
## Dropout(0.3),
## LSTM(32),
Dense(16, activation='relu'),
Dense(1, activation='sigmoid')
## ])
# Training on 2 years of hourly data (17,520 samples)
# Model had 87,000+ parameters
# Result: 91% training accuracy, 52% test accuracy (no better than random)

Statistical evidence
## :
The lesson
: Models must adapt to regime changes or be
regime-aware.
Failure Mode 3: Look-Ahead Bias
The problem
: Accidentally using future information to
make predictions about the past. This is devastatingly
common and makes backtests meaningless.
Subtle ways this happens
## :
## 1.
Data normalization done wrong
## :
# Testing stationarity of Bitcoin returns
from statsmodels.tsa.stattools import adfuller
def test_stationarity(timeseries):
result = adfuller(timeseries)
print(f'ADF Statistic: {result[0]}')
print(f'p-value: {result[1]}')
return result[1] < 0.05  # True if stationary
# Testing different periods
bull_market = btc_returns['2020-01':'2021-11']
bear_market = btc_returns['2022-01':'2022-12']
print("Bull market stationary:", test_stationarity(bull_market))
## # Output: False (p-value: 0.23)
print("Bear market stationary:", test_stationarity(bear_market))
## # Output: False (p-value: 0.19)
# Bitcoin returns are non-stationary - a major challenge for ML
# WRONG: Normalizing entire dataset before train/test split
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
# This uses future data statistics to normalize past data
X_scaled = scaler.fit_transform(X_entire_dataset)
# Then splitting
## X_train, X_test = X_scaled[:split], X_scaled[split:]
# RIGHT: Fit scaler only on training data
scaler = StandardScaler()

## 2.
Feature engineering with non-causal data
## :
## 3.
Survival bias
: Training only on assets that survived to
present day, ignoring the thousands of dead coins.
The lesson
: Extreme diligence in data pipeline
construction. One look-ahead bug destroys the entire
model’s validity.
## Failure Mode 4: Ignoring Transaction Costs
The problem
: ML models often predict tiny edges (51–
52% win rate). Transaction costs eliminate the edge.
Reality check
## :
The lesson
: Transaction-aware modeling is mandatory.
Edge must be significantly larger than costs.
X_train_scaled = scaler.fit_transform(X_train)
# Use training statistics to transform test data
X_test_scaled = scaler.transform(X_test)
# WRONG: Using future volatility to predict price
df['future_volatility'] = df['returns'].rolling(24).std().shift(-24)
# This looks ahead 24 hours
# RIGHT: Only use past volatility
df['past_volatility'] = df['returns'].rolling(24).std()
# Model predicts 52% win rate with 0.5% average gain per trade
theoretical_edge = 0.52 * 0.005 - 0.48 * 0.005
print(f"Theoretical edge per trade: {theoretical_edge:.4%}")
# Output: 0.02% per trade
# But actual costs:
exchange_fee = 0.001  # 0.1% per side
slippage = 0.0005     # 0.05% average
total_cost = (exchange_fee + slippage) * 2  # Round trip
print(f"Round-trip cost: {total_cost:.4%}")
# Output: 0.30% per trade
# Net edge after costs: -0.28% per trade (losing money!)

Edge must be significantly larger than costs.
## Failure Mode 5: Insufficient Feature Engineering
The problem
: Feeding raw price data into complex
neural networks and hoping they “figure it out.”
## Reality
: While theoretically neural networks can learn
any function, in practice with limited data, they need
help through thoughtful features.
What doesn’t work
## :
# Just raw prices and volumes
features = ['open', 'high', 'low', 'close', 'volume']
What works better
## :
The lesson
: Domain expertise in feature engineering
often matters more than model sophistication.
## Models That Actually Work: A Practical
Ta xo n o m y
After seven years of production experience, here are the
ML approaches that have proven effective in live crypto
trading:
Tier 1: Gradient Boosting Models (XGBoost, LightGBM)
Why they work
## :
# Engineered features that encode market structure
features = [
## 'returns', 'log_returns', 'volatility',
## 'volume_change', 'volume_momentum',
## 'price_momentum_1h', 'price_momentum_4h', 'price_momentum_24h',
## 'rsi', 'macd', 'bollinger_position',
## 'order_book_imbalance', 'trade_flow_imbalance',
## 'realized_volatility', 'garman_klass_volatility',
# ... market microstructure features
## ]

Why they work
## :
Handle non-linear relationships effectively
Resistant to overfitting (with proper tuning)
Work well with limited data (10,000+ samples
sufficient)
Naturally handle missing data
Fast training and prediction
Interpretable (feature importance)
Our primary use case
: Short-term price direction
prediction (1–4 hour horizons)
Implementation example
## :
import lightgbm as lgb
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
class CryptoDirectionModel:
## """
LightGBM model for predicting short-term price direction
## """
def __init__(self):
self.model = None
self.feature_names = None

def create_features(self, df):
## """
Create features from OHLCV data
## """
features = pd.DataFrame(index=df.index)

# Price-based features
features['returns'] = df['close'].pct_change()
features['log_returns'] = np.log(df['close'] / df['close'].shift(1))

# Momentum features (multiple timeframes)
for period in [3, 6, 12, 24]:
features[f'momentum_{period}h'] = (
df['close'] / df['close'].shift(period) - 1
## )

# Volatility features
features['volatility_6h'] = features['returns'].rolling(6).std()
features['volatility_24h'] = features['returns'].rolling(24).std()

# Volume features
features['volume_change'] = df['volume'].pct_change()
features['volume_momentum_6h'] = (
df['volume'] / df['volume'].rolling(6).mean()
## )

# Technical indicators

# Technical indicators
features['rsi_14'] = self.calculate_rsi(df['close'], 14)
features['macd'], features['macd_signal'] = self.calculate_macd(df['close'])

# Order flow features (if available)
if 'bid_volume' in df.columns:
features['order_imbalance'] = (
(df['bid_volume'] - df['ask_volume']) /
(df['bid_volume'] + df['ask_volume'])
## )

return features.dropna()

def create_labels(self, df, forward_hours=4, threshold=0.005):
## """
Create labels: 1 if price rises >0.5% in next 4 hours, 0 otherwise
## """
future_return = (
df['close'].shift(-forward_hours) / df['close'] - 1
## )
labels = (future_return > threshold).astype(int)
return labels

def train(self, df, validation_split=0.2):
## """
Train model with time-aware validation
## """
# Create features and labels
X = self.create_features(df)
y = self.create_labels(df)

# Align features and labels
valid_idx = X.index.intersection(y.index)
## X = X.loc[valid_idx]
y = y.loc[valid_idx]

# Time-based split (no shuffling - preserves temporal order)
split_point = int(len(X) * (1 - validation_split))
## X_train, X_val = X[:split_point], X[split_point:]
y_train, y_val = y[:split_point], y[split_point:]

# Model parameters (conservative to prevent overfitting)
params = {
## 'objective': 'binary',
## 'metric': 'auc',
## 'num_leaves': 31,
## 'learning_rate': 0.05,
## 'feature_fraction': 0.8,
## 'bagging_fraction': 0.8,
## 'bagging_freq': 5,
## 'max_depth': 6,
## 'min_data_in_leaf': 100,
## 'verbose': -1
## }

# Train with early stopping
train_data = lgb.Dataset(X_train, label=y_train)
val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

self.model = lgb.train(
params,
train_data,
num_boost_round=1000,
valid_sets=[train_data, val_data],
callbacks=[lgb.early_stopping(stopping_rounds=50)]
## )

Production performance
(our BTC 4h direction model):

self.feature_names = X.columns.tolist()

## # Evaluation
y_pred_val = self.model.predict(X_val)
auc_score = roc_auc_score(y_val, y_pred_val)

print(f"Validation AUC: {auc_score:.4f}")

return self.model

def predict_probability(self, df):
## """
Predict probability of upward movement
## """
X = self.create_features(df)
probabilities = self.model.predict(X)
return probabilities

def get_feature_importance(self, top_n=15):
## """
Get most important features
## """
importance = self.model.feature_importance(importance_type='gain')
feature_importance = pd.DataFrame({
'feature': self.feature_names,
'importance': importance
}).sort_values('importance', ascending=False)

return feature_importance.head(top_n)

## @staticmethod
def calculate_rsi(prices, period=14):
"""Calculate RSI indicator"""
delta = prices.diff()
gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
rs = gain / loss
rsi = 100 - (100 / (1 + rs))
return rsi

## @staticmethod
def calculate_macd(prices, fast=12, slow=26, signal=9):
"""Calculate MACD indicator"""
ema_fast = prices.ewm(span=fast).mean()
ema_slow = prices.ewm(span=slow).mean()
macd = ema_fast - ema_slow
macd_signal = macd.ewm(span=signal).mean()
return macd, macd_signal
# Usage example
model = CryptoDirectionModel()
model.train(historical_data)
# Get predictions
current_prob = model.predict_probability(current_data)
print(f"Probability of 0.5%+ rise in next 4h: {current_prob[-1]:.2%}")
# Understand what drives predictions
print("\nTop features:")
print(model.get_feature_importance())

Production performance
(our BTC 4h direction model):
AUC: 0.58 (modest but consistent edge)
Accuracy: 54% (after accounting for uncertainty
filtering)
Sharpe ratio: 1.4 (after transaction costs)
Stability: Performance consistent across different
market regimes
Key insights
## :
We only trade when probability exceeds 60% or falls
below 40% (ignore 40–60% range)
This filters ~70% of potential trades, keeping only
high-conviction signals
Dramatically reduces transaction costs and improves
risk-adjusted returns
Tier 2: Ensemble Methods (Model Stacking)
Why they work
## :
Combine diverse models to reduce individual model
biases
More robust to regime changes
Can capture different types of patterns
Our approach
: Stack multiple specialized models
class EnsemblePredictor:
## """
Ensemble of specialized models for robust predictions
## """
def __init__(self):
self.models = {
'direction_4h': CryptoDirectionModel(),  # Short-term direction
'volatility': VolatilityRegressor(),      # Volatility forecast
'regime': RegimeClassifier()              # Market regime
## }
self.meta_model = None

def train_base_models(self, train_data):

Production performance
## :
AUC: 0.62 (improvement over single models)
More stable across different market conditions
Reduced max drawdown by 30% vs. single-model
approach
## Tier 3: Online Learning Models
Why they work
## :
Adapt to changing market conditions in real-time
Don’t require complete retraining
Naturally handle non-stationarity
The challenge
: Most ML frameworks don’t support
online learning well.
def train_base_models(self, train_data):
"""Train all base models"""
for name, model in self.models.items():
print(f"Training {name}...")
model.train(train_data)

def train_meta_model(self, val_data):
## """
Train meta-model that learns how to combine base model predictions
## """
# Get predictions from all base models
base_predictions = {}
for name, model in self.models.items():
base_predictions[name] = model.predict(val_data)

# Create meta-features
X_meta = pd.DataFrame(base_predictions)
y_meta = self.create_labels(val_data)

# Train simple logistic regression as meta-model
from sklearn.linear_model import LogisticRegression
self.meta_model = LogisticRegression()
self.meta_model.fit(X_meta, y_meta)

def predict(self, current_data):
"""Final ensemble prediction"""
base_predictions = {}
for name, model in self.models.items():
base_predictions[name] = model.predict(current_data)

X_meta = pd.DataFrame([base_predictions])
final_prediction = self.meta_model.predict_proba(X_meta)[0, 1]

return final_prediction

online learning well.
Our solution
: River (formerly Creme) library for online
## ML
Production performance
## :
from river import linear_model, preprocessing, compose, metrics
class OnlineAdaptiveModel:
## """
Online learning model that adapts to market changes
## """
def __init__(self):
# Create online learning pipeline
self.model = compose.Pipeline(
preprocessing.StandardScaler(),
linear_model.LogisticRegression()
## )
self.metric = metrics.ROCAUC()

def update_and_predict(self, features, label=None):
## """
Predict, then update model with new data
## """
# Make prediction first
y_pred = self.model.predict_proba_one(features)

# Then update with true label (if available)
if label is not None:
self.model.learn_one(features, label)
self.metric.update(label, y_pred.get(True, 0))

return y_pred.get(True, 0)  # Return probability of positive class

def get_current_performance(self):
"""Get rolling performance metric"""
return self.metric.get()
# Usage in production
online_model = OnlineAdaptiveModel()
for timestamp, data in live_data_stream:
features = extract_features(data)

## # Predict
prediction = online_model.update_and_predict(features)

# Wait for outcome, then update
actual_outcome = get_actual_outcome(timestamp, hours_ahead=4)
online_model.update_and_predict(features, actual_outcome)

# Monitor performance
if timestamp % 100 == 0:
print(f"Current AUC: {online_model.get_current_performance():.4f}")

Adapts within hours to new market conditions
Particularly effective during regime transitions
Requires careful monitoring (can adapt to noise if not
constrained)
Tier 4: Reinforcement Learning (Cautiously)
Why it could work
## :
Naturally frames trading as sequential decision-
making
Can learn complex multi-step strategies
Optimizes for cumulative returns, not just prediction
accuracy
Why it usually fails
## :
Requires massive amounts of data (millions of
episodes)
Unstable training
Difficult to debug when things go wrong
Often learns to exploit simulation artifacts rather
than real patterns
Our limited success
: Using RL for position sizing, not
entry/exit signals
import gym
import numpy as np
from stable_baselines3 import PPO
class PositionSizingEnv(gym.Env):
## """
RL environment for learning optimal position sizing
## """
def __init__(self, data, base_signals):
super().__init__()
self.data = data
self.base_signals = base_signals  # From our direction model
self.current_step = 0
self.position = 0
self.cash = 100000

self.cash = 100000

# Action space: position size (0 to 1.0 of capital)
self.action_space = gym.spaces.Box(
low=0, high=1, shape=(1,), dtype=np.float32
## )

# Observation space: market features + current position
self.observation_space = gym.spaces.Box(
low=-np.inf, high=np.inf, shape=(10,), dtype=np.float32
## )

def reset(self):
self.current_step = 0
self.position = 0
self.cash = 100000
return self._get_observation()

def step(self, action):
# Action is desired position size
desired_position_size = action[0]

# Get current signal and market state
current_signal = self.base_signals[self.current_step]
current_price = self.data['close'].iloc[self.current_step]
next_price = self.data['close'].iloc[self.current_step + 1]

# Calculate return
if current_signal > 0.6:  # Bullish signal
# RL determines how much to bet
actual_position = desired_position_size * self.cash / current_price
pnl = actual_position * (next_price - current_price)
else:
pnl = 0  # No trade

self.cash += pnl
self.current_step += 1

# Reward: Sharpe-like (return / volatility)
reward = pnl / (self.cash * 0.02)  # Normalized by portfolio and volatility

done = self.current_step >= len(self.data) - 1

return self._get_observation(), reward, done, {}

def _get_observation(self):
# Current state: market features + position
idx = self.current_step
obs = np.array([
self.data['returns'].iloc[idx],
self.data['volatility_24h'].iloc[idx],
self.base_signals[idx],
self.position / self.cash if self.cash > 0 else 0,
# ... additional features
], dtype=np.float32)
return obs
# Training (offline, on historical data)
env = PositionSizingEnv(train_data, train_signals)
model = PPO("MlpPolicy", env, verbose=1)
model.learn(total_timesteps=100000)
# Using in production
def determine_position_size(market_state, base_signal):
obs = create_observation(market_state, base_signal)
position_size = model.predict(obs, deterministic=True)[0]
return position_size

Production performance
## :
~15% improvement in risk-adjusted returns over
fixed sizing
Works because task is well-defined (position sizing
given a signal)
Still requires extensive monitoring and periodic
retraining
Honest assessment
: RL is not our primary tool. We use it
only for specific, constrained problems where simpler
approaches have failed.
## The Feature Engineering That Actually Matters
I’ve found that 70% of model performance comes from
features, 30% from model choice.
## Feature Categories That Work
- Multi-Timeframe Momentum
Why it works
: Different timeframes capture different
trader types (scalpers, swing traders, position traders).
Their collective behavior predicts short-term moves.
return position_size
def create_momentum_features(df):
"""Momentum across multiple timeframes captures trend strength"""
features = pd.DataFrame(index=df.index)

for hours in [1, 4, 12, 24, 72, 168]:  # 1h to 1 week
features[f'momentum_{hours}h'] = (
df['close'] / df['close'].shift(hours) - 1
## )

# Also capture acceleration (momentum of momentum)
features[f'momentum_acceleration_{hours}h'] = (
features[f'momentum_{hours}h'].diff()
## )

return features

## 2.
Realized Volatility (Multiple Estimators)
Why it works
: Volatility is more predictable than price
direction. Volatility regimes strongly influence optimal
strategy behavior.
## 3.
## Order Flow Imbalance
def create_volatility_features(df):
"""Multiple volatility estimators for robustness"""
features = pd.DataFrame(index=df.index)

# Simple realized volatility
returns = df['close'].pct_change()
features['rv_6h'] = returns.rolling(6).std() * np.sqrt(365*24)  # Annualized
features['rv_24h'] = returns.rolling(24).std() * np.sqrt(365*24)

# Parkinson (uses high/low, more efficient)
features['parkinson_24h'] = np.sqrt(
## 1/(4*np.log(2)) *
## (np.log(df['high']/df['low'])**2).rolling(24).mean()
) * np.sqrt(365*24)

# Garman-Klass (uses OHLC, even more efficient)
hl = np.log(df['high']/df['low'])**2
co = np.log(df['close']/df['open'])**2
features['gk_24h'] = np.sqrt(
## 0.5*hl.rolling(24).mean() - (2*np.log(2)-1)*co.rolling(24).mean()
) * np.sqrt(365*24)

# Volatility changes (regime shifts)
features['vol_change_6h'] = features['rv_6h'] / features['rv_24h']

return features
def create_orderflow_features(df):
## """
Order book and trade flow features (exchange API required)
## """
features = pd.DataFrame(index=df.index)

# Order book imbalance (bid vs ask pressure)
total_liquidity = df['bid_volume_sum'] + df['ask_volume_sum']
features['ob_imbalance'] = (
(df['bid_volume_sum'] - df['ask_volume_sum']) / total_liquidity
## )

# Trade flow (buy vs sell market orders)
total_trades = df['buy_volume'] + df['sell_volume']
features['trade_imbalance'] = (

Why it works
: Order flow reveals actual buying/selling
pressure, not just price results. Strong predictor for
short-term moves (minutes to hours).
## 4.
Volatility-Adjusted Returns
Why it works
: Raw returns are noisy. Volatility-adjusted
returns separate skill from luck and are more stable
predictors.
## 5.
## Market Microstructure
(df['buy_volume'] - df['sell_volume']) / total_trades
## )

# Imbalance momentum
features['imbalance_momentum'] = (
features['trade_imbalance'].diff().rolling(6).mean()
## )

return features
def create_risk_adjusted_features(df):
"""Returns normalized by volatility for comparability"""
features = pd.DataFrame(index=df.index)

returns = df['close'].pct_change()
volatility = returns.rolling(24).std()

# Sharpe-like: return normalized by volatility
features['risk_adj_return_6h'] = (
returns.rolling(6).mean() / (volatility + 1e-8)
## )

# Sortino-like: return normalized by downside volatility
downside_vol = returns[returns < 0].rolling(24).std()
features['sortino_return_6h'] = (
returns.rolling(6).mean() / (downside_vol + 1e-8)
## )

return features
def create_microstructure_features(df):
"""Price impact and liquidity measures"""
features = pd.DataFrame(index=df.index)


Why it works
: Microstructure measures capture
transaction costs and liquidity, critical for execution
quality.
## Model Evaluation: Beyond Accuracy
Accuracy is almost useless for trading models. Here’s
what actually matters:
Metric 1: Precision-Recall at Decision Thresholds

# Amihud illiquidity: price impact per dollar traded
features['illiquidity'] = (
abs(df['close'].pct_change()) / (df['volume'] * df['close'] + 1e-8)
## ).rolling(24).mean()

# Bid-ask spread (when available)
if 'bid' in df.columns and 'ask' in df.columns:
features['spread'] = (df['ask'] - df['bid']) / df['close']
features['spread_ma'] = features['spread'].rolling(24).mean()

# Effective spread from trades
features['effective_spread'] = (
2 * abs(df['close'] - (df['high'] + df['low'])/2)
) / df['close']

return features
def evaluate_trading_model(y_true, y_pred_proba, trading_threshold=0.6):
## """
Evaluate model at actual trading threshold
## """
# We only trade when probability > 60% or < 40%
trade_mask = (y_pred_proba > trading_threshold) | (y_pred_proba < (1-trading_threshold))

# Filter to actual trades
y_true_trades = y_true[trade_mask]
y_pred_trades = (y_pred_proba[trade_mask] > 0.5).astype(int)

from sklearn.metrics import precision_score, recall_score, f1_score

precision = precision_score(y_true_trades, y_pred_trades)
recall = recall_score(y_true_trades, y_pred_trades)
f1 = f1_score(y_true_trades, y_pred_trades)

print(f"At threshold {trading_threshold}:")
print(f"  Precision: {precision:.3f}")
print(f"  Recall: {recall:.3f}")
print(f"  F1 Score: {f1:.3f}")
print(f"  Trade frequency: {trade_mask.sum() / len(trade_mask):.1%}")

return precision, recall, f1

Why it matters
: We don’t care about accuracy on all
predictions, only on trades we actually take.
Metric 2: Simulated P&L
Why it matters
: This is the actual performance that
matters. A model with 60% accuracy but horrible timing
can lose money.
Metric 3: Regime-Stratified Performance
def calculate_strategy_pnl(df, predictions, threshold=0.6, cost_per_trade=0.002):
## """
Calculate actual P&L including transaction costs
## """
positions = np.zeros(len(df))

# Take position when confident
positions[predictions > threshold] = 1      # Long
positions[predictions < (1-threshold)] = -1  # Short (if allowed)

# Calculate returns
returns = df['close'].pct_change()
strategy_returns = positions.shift(1) * returns  # Shift to avoid look-ahead

# Subtract transaction costs
position_changes = positions.diff().abs()
costs = position_changes * cost_per_trade
strategy_returns_after_costs = strategy_returns - costs

# Calculate metrics
cumulative_return = (1 + strategy_returns_after_costs).prod() - 1
sharpe = strategy_returns_after_costs.mean() / strategy_returns_after_costs.std() * np.sqrt(365*24)
max_dd = (strategy_returns_after_costs.cumsum().cummax() - strategy_returns_after_costs.cumsum()).max()

print(f"Cumulative Return: {cumulative_return:.2%}")
print(f"Sharpe Ratio: {sharpe:.2f}")
print(f"Max Drawdown: {max_dd:.2%}")
print(f"Number of trades: {position_changes.sum()}")

return strategy_returns_after_costs
def evaluate_by_regime(df, predictions, y_true):
## """
Check if model works in different market conditions
## """
# Define regimes
volatility = df['close'].pct_change().rolling(24).std()


Why it matters
: A model that only works in bull markets
or low volatility is fragile. We need consistent
performance across regimes.
## Production Deployment: The Hard Parts
Getting a model to work in backtest is 20% of the
challenge. Production is the other 80%.
Challenge 1: Real-Time Feature Computation
The problem
: Features that take seconds to compute in
Python are too slow for live trading.
Our solution
: Pre-compute as much as possible, use
compiled code for the rest.

low_vol = volatility < volatility.quantile(0.33)
high_vol = volatility > volatility.quantile(0.66)

from sklearn.metrics import roc_auc_score

print("Low volatility regime:")
print(f"  AUC: {roc_auc_score(y_true[low_vol], predictions[low_vol]):.3f}")

print("Medium volatility regime:")
mid_vol = ~low_vol & ~high_vol
print(f"  AUC: {roc_auc_score(y_true[mid_vol], predictions[mid_vol]):.3f}")

print("High volatility regime:")
print(f"  AUC: {roc_auc_score(y_true[high_vol], predictions[high_vol]):.3f}")
# Slow: Computing from scratch every time
def slow_feature_computation(current_data, historical_data):
"""This recomputes everything - too slow"""
features = {}
features['momentum_24h'] = (
current_data['close'] / historical_data['close'].iloc[-24] - 1
## )
features['volatility_24h'] = (
historical_data['close'].pct_change().tail(24).std()
## )
# ... 50 more features
return features  # Takes 200ms - too slow for HFT
# Fast: Incremental updates
class IncrementalFeatureComputer:
"""Maintains state and updates incrementally"""
def __init__(self):
self.price_buffer = deque(maxlen=168)  # 1 week of hourly data
self.return_buffer = deque(maxlen=168)

Challenge 2: Model Versioning and A/B Testing
The problem
: You can’t just deploy a new model and
hope it works. You need to test carefully.
Our solution
: Shadow mode and gradual rollout
self.rolling_stats = {}

def update(self, new_candle):
"""Update with new data point (< 1ms)"""
self.price_buffer.append(new_candle['close'])

if len(self.price_buffer) > 1:
ret = new_candle['close'] / self.price_buffer[-2] - 1
self.return_buffer.append(ret)

# Incremental statistics
if len(self.return_buffer) >= 24:
self.rolling_stats['volatility_24h'] = np.std(
list(self.return_buffer)[-24:]
## )

if len(self.price_buffer) >= 24:
self.rolling_stats['momentum_24h'] = (
self.price_buffer[-1] / self.price_buffer[-24] - 1
## )

def get_features(self):
"""Retrieve pre-computed features (instant)"""
return self.rolling_stats
# In production
feature_computer = IncrementalFeatureComputer()
for candle in live_stream:
feature_computer.update(candle)  # <1ms
features = feature_computer.get_features()  # Instant
prediction = model.predict(features)  # ~5ms
## # Total: ~6ms (acceptable)
class ModelManager:
"""Manages multiple model versions in production"""
def __init__(self):
self.models = {
'production': load_model('model_v12_production.pkl'),
'shadow': load_model('model_v13_shadow.pkl')
## }
self.allocation = {'production': 1.0, 'shadow': 0.0}  # Shadow gets no capital

def predict(self, features, account_type='production'):
"""Get prediction from specified model"""
model = self.models[account_type]
prediction = model.predict(features)

# Log for comparison
log_prediction(account_type, prediction, features)

Challenge 3: Model Monitoring and Degradation
## Detection
The problem
: Models degrade silently. You need to
detect this before losing money.
Our solution
: Comprehensive monitoring dashboard

return prediction

def compare_performance(self, days=7):
"""Compare production vs shadow model"""
prod_performance = get_performance('production', days)
shadow_performance = get_performance('shadow', days)

print(f"Production (v12) Sharpe: {prod_performance['sharpe']:.2f}")
print(f"Shadow (v13) Sharpe: {shadow_performance['sharpe']:.2f}")

if shadow_performance['sharpe'] > prod_performance['sharpe'] * 1.1:
print("Shadow model outperforming! Consider gradual rollout.")

def gradual_rollout(self, new_allocation={'production': 0.8, 'shadow': 0.2}):
"""Allocate capital to new model gradually"""
self.allocation = new_allocation
print(f"New allocation: {new_allocation}")
## # Usage
model_mgr = ModelManager()
for data in live_stream:
features = extract_features(data)

# Production model (gets actual capital)
pred_prod = model_mgr.predict(features, 'production')

# Shadow model (tracked but no capital risked)
pred_shadow = model_mgr.predict(features, 'shadow')

# Execute based on production model only
execute_trade_if_confident(pred_prod)
# After 1 week of shadow testing
model_mgr.compare_performance(days=7)
# If shadow model better, gradually roll out
model_mgr.gradual_rollout({'production': 0.7, 'shadow': 0.3})
class ModelMonitor:
"""Monitor model performance and data quality in production"""
def __init__(self):
self.prediction_history = []
self.feature_history = []
self.outcome_history = []

def log_prediction(self, features, prediction, actual_outcome=None):
"""Log every prediction for monitoring"""
self.feature_history.append(features)
self.prediction_history.append(prediction)
if actual_outcome is not None:
self.outcome_history.append(actual_outcome)

self.outcome_history.append(actual_outcome)

def check_feature_drift(self, window=1000):
"""Detect if feature distributions have changed"""
recent_features = pd.DataFrame(self.feature_history[-window:])
baseline_features = pd.DataFrame(self.feature_history[-5000:-window])

from scipy.stats import ks_2samp

drift_detected = []
for col in recent_features.columns:
stat, pvalue = ks_2samp(
baseline_features[col].dropna(),
recent_features[col].dropna()
## )
if pvalue < 0.01:  # Significant drift
drift_detected.append(col)

if drift_detected:
alert(f"Feature drift detected: {drift_detected}")

return drift_detected

def check_prediction_calibration(self, window=1000):
"""Check if predicted probabilities match actual frequencies"""
recent_preds = self.prediction_history[-window:]
recent_outcomes = self.outcome_history[-window:]

# Bin predictions
bins = [0, 0.4, 0.5, 0.6, 1.0]
pred_bins = pd.cut(recent_preds, bins)

# Calculate actual rate in each bin
df = pd.DataFrame({
'pred_bin': pred_bins,
'outcome': recent_outcomes
## })

calibration = df.groupby('pred_bin')['outcome'].mean()

print("Calibration check:")
print(calibration)

# If poorly calibrated, alert
# e.g., if predictions of 60% are only correct 52% of the time

def check_performance_degradation(self, window=500):
"""Check if rolling performance is declining"""
from sklearn.metrics import roc_auc_score

# Calculate rolling AUC
rolling_aucs = []
for i in range(window, len(self.prediction_history)):
auc = roc_auc_score(
self.outcome_history[i-window:i],
self.prediction_history[i-window:i]
## )
rolling_aucs.append(auc)

# Check if recent AUC significantly below baseline
recent_auc = np.mean(rolling_aucs[-100:])
baseline_auc = np.mean(rolling_aucs[-1000:-100])

if recent_auc < baseline_auc - 0.05:  # 5pp drop
alert(f"Performance degradation! Recent AUC: {recent_auc:.3f}, Baseline: {baseline_auc:.3f}")
# Trigger model retraining or reduced capital allocation

What We Don’t Use (And Why)
To save you time and money, here are approaches we’ve
tested and abandoned:
Deep Learning for Price Prediction
What we tried
: LSTMs, GRUs, Transformers, Conv1D
networks
Why they failed
## :
Require massive data (we don’t have enough)
Prone to overfitting
Difficult to interpret
No better than gradient boosting on our tasks
Much slower to train and deploy
One exception
: CNNs for chart pattern recognition
(modest success, but not our primary tool)
Sentiment Analysis from Twitter
What we tried
: NLP models analyzing crypto Twitter
sentiment
Why it failed
## :
# Trigger model retraining or reduced capital allocation
# In production
monitor = ModelMonitor()
for data in live_stream:
features = extract_features(data)
prediction = model.predict(features)

# Log everything
monitor.log_prediction(features, prediction)

# Periodic checks (every 100 predictions)
if len(monitor.prediction_history) % 100 == 0:
monitor.check_feature_drift()
monitor.check_prediction_calibration()
monitor.check_performance_degradation()

Twitter is mostly noise and manipulation
Sentiment lags price more than leads it
Bots and coordinated campaigns distort signal
Compute cost vs. value not justified
Limited success
: Analyzing specific credible sources
(not general Twitter)
Genetic Algorithms for Strategy Optimization
What we tried
: Evolving trading strategies through
genetic algorithms
Why it failed
## :
Extreme overfitting to training period
Strategies too complex to understand
No way to know if strategy will generalize
Essentially data mining without theoretical
foundation
## Pure Technical Analysis Patterns
What we tried
: ML models to recognize head-and-
shoulders, triangles, etc.
Why it failed
## :
Patterns are subjective (humans disagree on
definitions)
Most “patterns” are retrofitted narrative, not
predictive
When quantified rigorously, most have no edge
What works instead
: Quantitative momentum and
mean-reversion features that capture the essence of
price action without subjective pattern matching

Practical Advice for Building Your Own Models
If you’re building ML trading models, here’s what I’d tell
my past self:
## Start Simple, Add Complexity Only When Justified
Most people skip steps 1–3 and jump to deep learning.
Then they spend months debugging models that never
work.
## Obsess Over Data Quality
## Progression:
- Simple rules (moving average crossovers) - get baseline
- Linear models (logistic regression) - add ML framework
- Gradient boosting (XGBoost/LightGBM) - capture non-linearity
- Ensembles - improve robustness
- Only then consider deep learning or RL
# Spend time on this
def validate_data_quality(df):
"""Check for common data issues"""
issues = []

# Check for duplicates
if df.index.duplicated().any():
issues.append("Duplicate timestamps found")

# Check for gaps
expected_freq = pd.infer_freq(df.index)
if expected_freq:
full_range = pd.date_range(df.index[0], df.index[-1], freq=expected_freq)
missing = full_range.difference(df.index)
if len(missing) > 0:
issues.append(f"{len(missing)} missing timestamps")

# Check for outliers (likely errors)
returns = df['close'].pct_change()
extreme_returns = returns[abs(returns) > 0.5]  # >50% moves likely errors
if len(extreme_returns) > 0:
issues.append(f"{len(extreme_returns)} extreme returns (possible errors)")

# Check for stuck prices
stuck = (df['close'].diff() == 0).rolling(10).sum() == 10
if stuck.any():
issues.append(f"Stuck prices detected (exchange issues?)")

if issues:
print("Data quality issues:")
for issue in issues:

Bad data → bad models. No amount of sophisticated ML
fixes corrupt inputs.
Paper Trade for Minimum 3 Months
Don’t risk real money until:
Model has 3+ months of paper trading results
Performance is consistent (not one lucky month)
You understand why it makes each prediction
You’ve stress-tested against historical crashes
You have monitoring and kill switches in place
## Allocate Capital Gradually
Month 1-3: Paper trading (zero capital)
Month 4-6: $1,000 (learning real execution)
Month 7-9: $10,000 (if still profitable)
## Month 10-12: $50,000 (if Sharpe > 1.0)
Year 2+: Scale gradually based on capacity
Never go all-in on a model, no matter how good the
backtest.
Final Thoughts: ML as Tool, Not Magic
After seven years using machine learning in production
crypto trading, my main conclusion:
ML is a powerful
tool, but it’s not magic
## .
The models that work are:
for issue in issues:
print(f"  - {issue}")
return False
else:
print("Data quality: OK")
return True
# Always run this before training
validate_data_quality(training_data)

Simple enough to understand
Robust across different markets
Based on sound financial intuition
Carefully monitored and maintained
Modest in their predictions
The models that fail are:
Black boxes even the creator doesn’t understand
Overfitted to one specific period
Based purely on data mining without theory
Deployed and forgotten
Promising unrealistic returns
The uncomfortable truth
: Most of our edge doesn’t come
from having more sophisticated models than
competitors. It comes from:
Better data quality
More thoughtful feature engineering
Stricter risk management
More disciplined execution
Continuous monitoring and improvement
Machine learning amplifies whatever foundation you
build on. If your foundation is solid (good data, sound
strategy, proper risk management), ML can enhance
returns.
If your foundation is weak, ML will just amplify your
losses faster.
Use ML as one tool in your toolkit, not the entire toolkit.

## Dr. Adrian Keller
is the founder of a private
cryptocurrency fund and former researcher at ETH
Zürich, specializing in AI-driven quantitative trading
strategies. His fund has been profitably deploying
machine learning models in production since 2018.
Follow for insights on quantitative trading, machine
learning in finance, and institutional crypto strategies.
Written by Adrian Keller
197 followers·1 following
Crypto investment expert & AI quant trading strategist.
Ph.D. in Financial Engineering from ETH Zürich. Founder
of private crypto fund.
## Follow



HelpStatusAboutCareersPressBlogStorePrivacyRules
TermsText to speech