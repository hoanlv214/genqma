import os

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

import numpy as np
import pandas as pd
import scipy.stats as stats

from sklearn.covariance import LedoitWolf
from sklearn.cluster import KMeans
from sklearn.neighbors import NearestNeighbors

QMA_DIR = os.path.abspath(os.path.dirname(__file__))
BASE_DIR = os.path.abspath(os.path.join(QMA_DIR, ".."))

def default_data_path(env_name: str, full_path: str, sample_path: str) -> str:
    configured = os.getenv(env_name)
    if configured:
        return configured
    return full_path if os.path.exists(full_path) else sample_path

HISTORICAL_DB_PATH = os.getenv(
    "QMA_HISTORICAL_DB_PATH",
    default_data_path(
        "QMA_HISTORICAL_DB_PATH",
        os.path.join(BASE_DIR, "tin_hieu", "json", "mexc", "funding_historical_analysis.csv"),
        os.path.join(QMA_DIR, "data", "sample_funding_historical_analysis.csv"),
    ),
)
BACKTEST_OUTCOME_PATH = os.getenv(
    "QMA_BACKTEST_OUTCOME_PATH",
    default_data_path(
        "QMA_BACKTEST_OUTCOME_PATH",
        os.path.join(BASE_DIR, "tin_hieu", "json", "mexc", "trading_analysis.csv"),
        os.path.join(QMA_DIR, "data", "sample_trading_analysis.csv"),
    ),
)
RANDOM_SEED = int(os.getenv("QMA_RANDOM_SEED", "42"))

class QMAEngine:
    def __init__(self):
        self.db = None
        self.features_matrix = None
        self.inv_cov_matrix = None
        self.kmeans = None
        self.cluster_meta = {}
        self.dataset_profile = {}
        self.validation_warnings = []
        self.empirical_nn_thresholds = {}
        self.empirical_nn_distances = np.array([])
        self.rng = np.random.default_rng(RANDOM_SEED)
        
        # Funding rate normalization caches
        self.token_counts = {}
        self.token_means = {}
        self.token_stds = {}
        self.global_mean_fr = 0.0
        self.global_std_fr = 0.0
        
        # Load and initialize
        self.initialize_engine()

    def initialize_engine(self):
        if not os.path.exists(HISTORICAL_DB_PATH) or not os.path.exists(BACKTEST_OUTCOME_PATH):
            raise FileNotFoundError("Historical database or backtest outcome files are missing.")
            
        features_df = pd.read_csv(HISTORICAL_DB_PATH)
        outcomes_df = pd.read_csv(BACKTEST_OUTCOME_PATH)
        raw_feature_rows = len(features_df)
        raw_outcome_rows = len(outcomes_df)

        # Create composite keys for exact merge
        features_df['composite_key'] = features_df['symbol'].astype(str).str.upper() + "_" + features_df['settleTime'].astype(str)
        outcomes_df['composite_key'] = outcomes_df['token'].astype(str).str.upper() + "_" + outcomes_df['settle_time'].astype(str)

        # Inner join to ensure every analog has a known PnL outcome
        merged = pd.merge(
            features_df,
            outcomes_df[['composite_key', 'profit_pct', 'candles_to_peak', 'risk_reward_ratio']],
            on='composite_key',
            how='inner'
        )
        joined_rows = len(merged)

        # Keep and clean core columns
        cols = ['symbol', 'settleTime', 'fundingRate', 'marketCap', 'FDV', 'circRatio', 'fromATH(%)', 'volume24h', 'amount', 'profit_pct', 'candles_to_peak', 'risk_reward_ratio']
        merged = merged.dropna(subset=cols)
        merged = merged[
            (merged['marketCap'] > 0)
            & (merged['FDV'] > 0)
            & (merged['volume24h'] > 0)
            & (merged['amount'] > 0)
            & (merged['circRatio'] > 0)
            & (merged['circRatio'] <= 1.5)
        ]
        self.db = merged.reset_index(drop=True)
        if len(self.db) < 50:
            raise ValueError(f"QMA needs at least 50 joined, clean samples; found {len(self.db)}.")

        self.dataset_profile = {
            "historical_feature_rows": int(raw_feature_rows),
            "backtest_outcome_rows": int(raw_outcome_rows),
            "joined_rows": int(joined_rows),
            "clean_joined_rows": int(len(self.db)),
            "unique_symbols": int(self.db["symbol"].nunique()),
            "time_min": int(self.db["settleTime"].min()),
            "time_max": int(self.db["settleTime"].max()),
        }

        # 1. Hybrid Funding Rate Z-score Calculation Setup
        token_groups = self.db.groupby('symbol')['fundingRate']
        self.token_counts = token_groups.size().to_dict()
        self.token_means = token_groups.mean().to_dict()
        self.token_stds = token_groups.std().fillna(0.001).to_dict()
        
        self.global_mean_fr = self.db['fundingRate'].mean()
        self.global_std_fr = self.db['fundingRate'].std()
        if not np.isfinite(self.global_std_fr) or self.global_std_fr == 0:
            self.global_std_fr = 0.001

        # Compute log-scaled features
        self.db['log_mc'] = np.log(self.db['marketCap'])
        self.db['log_fdv'] = np.log(self.db['FDV'])
        self.db['log_vol'] = np.log(self.db['volume24h'])
        
        # Corrected terminology from 'oi_leverage' to 'turnover_ratio'
        self.db['turnover_ratio'] = self.db['amount'] / self.db['marketCap']

        # Apply hybrid z-score to historical database
        local_z = []
        for _, row in self.db.iterrows():
            sym = row['symbol']
            fr = row['fundingRate']
            local_z.append(self.compute_fr_z(sym, fr))
        self.db['fr_z'] = local_z

        # Feature vector: [fr_z, log_mc, log_fdv, circRatio, fromATH(%), log_vol, turnover_ratio]
        self.feature_cols = ['fr_z', 'log_mc', 'log_fdv', 'circRatio', 'fromATH(%)', 'log_vol', 'turnover_ratio']
        self.feature_medians = self.db[self.feature_cols].median()
        self.feature_iqr = self.db[self.feature_cols].quantile(0.75) - self.db[self.feature_cols].quantile(0.25)
        self.feature_iqr = self.feature_iqr.replace(0, 1.0)
        self.features_matrix = self.transform_features(self.db[self.feature_cols]).values

        # 2. Robust Covariance Estimation via Ledoit-Wolf on robust-scaled features
        lw = LedoitWolf().fit(self.features_matrix)
        self.inv_cov_matrix = lw.precision_

        # 3. Time-Decay Weighting Setup (Half-life = 180 days)
        t_max = self.db['settleTime'].max()
        self.db['age_days'] = (t_max - self.db['settleTime']) / (1000 * 60 * 60 * 24)
        self.decay_rate = np.log(2) / 180.0
        self.db['decay_weight'] = np.exp(-self.decay_rate * self.db['age_days'])

        # 4. Regime Clustering via KMeans (4 clusters)
        self.n_clusters = min(4, len(self.db))
        self.kmeans = KMeans(n_clusters=self.n_clusters, random_state=RANDOM_SEED, n_init=20).fit(self.features_matrix)
        self.db['cluster_label'] = self.kmeans.labels_
        self.profile_clusters()
        self.fit_empirical_ood_reference()
        self.build_validation_warnings()

    def compute_fr_z(self, symbol, funding_rate):
        """Calculates funding rate Z-score using Hybrid Local/Global approach"""
        symbol = str(symbol).upper()
        count = self.token_counts.get(symbol, 0)
        if count >= 30:
            mean = self.token_means[symbol]
            std = self.token_stds[symbol]
        else:
            mean = self.global_mean_fr
            std = self.global_std_fr
        
        if std == 0:
            std = 0.001
        return (funding_rate - mean) / std

    def transform_features(self, raw_features):
        """Robust scales features with median/IQR and clips extreme leverage points."""
        if isinstance(raw_features, pd.Series):
            raw_features = raw_features.to_frame().T
        scaled = (raw_features.astype(float) - self.feature_medians) / self.feature_iqr
        return scaled.clip(lower=-8.0, upper=8.0)

    def profile_clusters(self):
        """Profiles the KMeans clusters to assign descriptive names and explanations"""
        for i in range(self.n_clusters):
            subset = self.db[self.db['cluster_label'] == i]
            if len(subset) == 0:
                continue
            avg_mc = subset['marketCap'].mean()
            avg_fr = subset['fundingRate'].mean()
            
            if avg_mc > 2.5e8:
                name = "Large-cap High Liquidity Regime"
                desc = "Stable regimes consisting of large-cap assets with solid circulating ratios and steady funding rates."
            elif avg_mc < 1e7:
                name = "Nano/Micro-cap Volatile Regime"
                desc = "High-risk, low market cap tokens (e.g., meme coins) characterized by low liquidity and high volatility."
            elif avg_fr < -0.01:
                name = "Extreme Funding Squeeze Regime"
                desc = "Tokens suffering from aggressive short positions, causing extremely negative funding rates and potential squeeze events."
            else:
                name = "Mid-cap Emerging Regime"
                desc = "Medium-sized tokens showing balanced circulating supplies, regular volumes, and moderate funding rates."
            
            self.cluster_meta[i] = {
                "name": name,
                "description": desc,
                "support": int(len(subset)),
                "avg_profit_pct": float(subset["profit_pct"].mean()),
                "win_rate": float((subset["profit_pct"] > 0).mean() * 100),
            }

    def fit_empirical_ood_reference(self):
        """Build an empirical nearest-neighbor distance reference for OOD checks."""
        n_neighbors = 2 if len(self.features_matrix) > 1 else 1
        nn = NearestNeighbors(
            n_neighbors=n_neighbors,
            metric="mahalanobis",
            metric_params={"VI": self.inv_cov_matrix},
            algorithm="brute",
        )
        nn.fit(self.features_matrix)
        distances, _ = nn.kneighbors(self.features_matrix)
        reference = distances[:, 1] if n_neighbors == 2 else distances[:, 0]
        self.empirical_nn_distances = reference
        self.empirical_nn_thresholds = {
            "p90": float(np.percentile(reference, 90)),
            "p95": float(np.percentile(reference, 95)),
            "p99": float(np.percentile(reference, 99)),
        }

    def build_validation_warnings(self):
        """Record honest caveats that should be visible in a hackathon demo."""
        warnings = []
        if self.dataset_profile["clean_joined_rows"] < 500:
            warnings.append("Small clean joined sample; confidence intervals are evidence-quality diagnostics, not tradable guarantees.")
        if (self.db["profit_pct"] > 0).mean() > 0.9:
            warnings.append("Outcome labels are peak-profit based and mostly positive; benchmark/calibration tests are required before calling this alpha.")
        if self.dataset_profile["joined_rows"] / max(self.dataset_profile["historical_feature_rows"], 1) < 0.25:
            warnings.append("Large join drop-off between funding events and outcomes; selection bias must be addressed before production.")
        self.validation_warnings = warnings

    def validate_query(self, query):
        required = ["fundingRate", "marketCap", "FDV", "circRatio", "fromATH", "volume24h"]
        missing = [key for key in required if key not in query]
        if missing:
            raise ValueError(f"Missing required query fields: {', '.join(missing)}")

        positive_fields = ["marketCap", "FDV", "volume24h"]
        for field in positive_fields:
            if float(query[field]) <= 0:
                raise ValueError(f"{field} must be positive.")
        if float(query["circRatio"]) <= 0 or float(query["circRatio"]) > 1.5:
            raise ValueError("circRatio must be in the range (0, 1.5].")

    def analyze_signal(self, query: dict) -> dict:
        """Runs the Analog Retrieval pipeline for a live query vector"""
        self.validate_query(query)
        symbol = query.get("symbol", "UNKNOWN").upper()
        live_fr = float(query["fundingRate"])
        live_mc = float(query["marketCap"])
        live_fdv = float(query["FDV"])
        live_cr = float(query["circRatio"])
        live_ath = float(query["fromATH"])
        live_vol = float(query["volume24h"])
        # If openInterest is provided, we use it. Otherwise, amount is a relative proxy.
        live_amount = float(query.get("amount") or live_vol * 0.1) # fallback turnover proxy
        live_turnover = live_amount / live_mc

        # Compute z-score
        live_fr_z = self.compute_fr_z(symbol, live_fr)

        # Build raw and robust-scaled feature vector
        raw_live_vector = pd.DataFrame([{
            "fr_z": live_fr_z,
            "log_mc": np.log(live_mc),
            "log_fdv": np.log(live_fdv),
            "circRatio": live_cr,
            "fromATH(%)": live_ath,
            "log_vol": np.log(live_vol),
            "turnover_ratio": live_turnover,
        }], columns=self.feature_cols)
        live_vector = self.transform_features(raw_live_vector).values[0]

        raw_feature_echo = np.array([
            live_fr_z,
            np.log(live_mc),
            np.log(live_fdv),
            live_cr,
            live_ath,
            np.log(live_vol),
            live_turnover
        ])

        # Compute Mahalanobis Distance (Vectorized)
        diff = self.features_matrix - live_vector
        distances = np.sqrt(np.sum(np.dot(diff, self.inv_cov_matrix) * diff, axis=1))

        # Determine target K dynamically
        K = min(max(12, int(np.sqrt(len(self.db)) * 1.5)), 50)
        ranked = self.db.assign(
            distance=distances,
            similarity=self.distance_to_similarity(distances),
        )
        neighbors = ranked.nsmallest(K, 'distance').copy()

        # Out-of-Distribution (OOD): chi-square plus empirical nearest-neighbor reference
        d2_min = neighbors['distance'].iloc[0] ** 2
        p_value = stats.chi2.sf(d2_min, df=7)
        empirical_nn_distance = float(neighbors['distance'].iloc[0])
        empirical_threshold = self.empirical_nn_thresholds.get("p99", float("inf"))
        empirical_percentile = float((self.empirical_nn_distances <= empirical_nn_distance).mean() * 100)
        is_ood = (p_value < 0.01) or (empirical_nn_distance > empirical_threshold)

        # Predict cluster regime
        query_cluster = int(self.kmeans.predict(live_vector.reshape(1, -1))[0])
        cluster_info = self.cluster_meta.get(query_cluster, {"name": "Unknown Regime", "description": "No cluster profile matches."})

        # Calculate distance-aware, time-decay weighted statistics
        norm_weights = self.compute_neighbor_weights(neighbors)
        effective_sample_size = float(1.0 / np.sum(np.square(norm_weights)))

        profits = neighbors['profit_pct'].values
        weighted_win_rate = np.sum(norm_weights * (profits > 0)) * 100
        weighted_avg_profit = np.sum(norm_weights * profits)

        # Weighted percentiles
        p10 = self.weighted_percentile(profits, norm_weights, 10)
        p25 = self.weighted_percentile(profits, norm_weights, 25)
        median = self.weighted_percentile(profits, norm_weights, 50)
        p75 = self.weighted_percentile(profits, norm_weights, 75)
        p90 = self.weighted_percentile(profits, norm_weights, 90)
        max_loss = np.min(profits)

        # 5. Bootstrap Confidence Intervals
        bootstrap_win_rates = []
        bootstrap_avg_profits = []
        bootstrap_rounds = 500
        for _ in range(bootstrap_rounds):
            sample = self.rng.choice(profits, size=K, replace=True, p=norm_weights)
            bootstrap_win_rates.append(np.sum(sample > 0) / K * 100)
            bootstrap_avg_profits.append(np.mean(sample))

        ci_win_rate = [float(np.percentile(bootstrap_win_rates, 2.5)), float(np.percentile(bootstrap_win_rates, 97.5))]
        ci_avg_profit = [float(np.percentile(bootstrap_avg_profits, 2.5)), float(np.percentile(bootstrap_avg_profits, 97.5))]

        # Compile neighbors list
        analog_list = []
        for _, row in neighbors.head(10).iterrows():
            analog_list.append({
                "symbol": row['symbol'],
                "fundingRate": float(row['fundingRate']),
                "marketCap": float(row['marketCap']),
                "profit_pct": float(row['profit_pct']),
                "similarity": float(row['similarity']),
                "age_days": float(row['age_days']),
                "decay_weight": float(row['decay_weight']),
                "distance": float(row["distance"]),
            })

        risk_flags = self.build_risk_flags(
            is_ood=is_ood,
            p_value=p_value,
            effective_sample_size=effective_sample_size,
            weighted_win_rate=weighted_win_rate,
            p10=p10,
            median=median,
        )

        return {
            "query_symbol": symbol,
            "is_ood": bool(is_ood),
            "ood_p_value": float(p_value),
            "ood_empirical_nn_distance": empirical_nn_distance,
            "ood_empirical_p99_threshold": float(empirical_threshold),
            "ood_empirical_percentile": empirical_percentile,
            "matched_k": K,
            "average_similarity": float(neighbors['similarity'].mean()),
            "regime_cluster": cluster_info["name"],
            "regime_description": cluster_info["description"],
            "regime_support": int(cluster_info.get("support", 0)),
            "weighted_win_rate": float(weighted_win_rate),
            "ci_win_rate_95": ci_win_rate,
            "weighted_avg_profit": float(weighted_avg_profit),
            "ci_avg_profit_95": ci_avg_profit,
            "percentiles": {
                "P10": float(p10),
                "P25": float(p25),
                "P50_median": float(median),
                "P75": float(p75),
                "P90": float(p90),
                "worst_case_max_loss": float(max_loss)
            },
            "effective_sample_size": effective_sample_size,
            "bootstrap_rounds": bootstrap_rounds,
            "distance_summary": {
                "nearest": float(neighbors["distance"].min()),
                "median_neighbor": float(neighbors["distance"].median()),
                "farthest_neighbor": float(neighbors["distance"].max()),
            },
            "query_features": {
                name: float(value) for name, value in zip(self.feature_cols, raw_feature_echo)
            },
            "data_quality": self.dataset_profile,
            "validation_warnings": self.validation_warnings,
            "risk_flags": risk_flags,
            "analogs": analog_list
        }

    def distance_to_similarity(self, distances):
        """Map distances to an interpretable 0-1 score using empirical p95 scale."""
        scale = self.empirical_nn_thresholds.get("p95") or np.percentile(distances, 95)
        scale = max(float(scale), 1e-9)
        return np.exp(-distances / scale)

    def compute_neighbor_weights(self, neighbors):
        distances = neighbors["distance"].values.astype(float)
        decay_weights = neighbors["decay_weight"].values.astype(float)
        positive_distances = distances[distances > 0]
        tau = np.median(positive_distances) if len(positive_distances) else 1.0
        tau = max(float(tau), 1e-9)
        distance_weights = np.exp(-distances / tau)
        weights = decay_weights * distance_weights
        weight_sum = np.sum(weights)
        if not np.isfinite(weight_sum) or weight_sum <= 0:
            return np.ones(len(neighbors)) / len(neighbors)
        return weights / weight_sum

    def build_risk_flags(self, is_ood, p_value, effective_sample_size, weighted_win_rate, p10, median):
        flags = []
        if is_ood:
            flags.append("OOD: nearest analog is outside the empirical training envelope.")
        if p_value < 0.05:
            flags.append("Low chi-square p-value: feature vector is statistically unusual.")
        if effective_sample_size < 8:
            flags.append("Low effective sample size: result depends on a small number of analogs.")
        if weighted_win_rate > 95:
            flags.append("Win rate is unusually high; inspect label construction and benchmark calibration.")
        if p10 < 0 and median > 0:
            flags.append("Left-tail loss exists despite positive median outcome.")
        if not flags:
            flags.append("No hard statistical alert, but this remains retrieval evidence rather than a forecast.")
        return flags

    def weighted_percentile(self, values, weights, percentile):
        """Computes weighted percentile from sorted values and normalized weights"""
        sorted_idx = np.argsort(values)
        sorted_val = values[sorted_idx]
        sorted_wt = weights[sorted_idx]
        cum_wt = np.cumsum(sorted_wt)
        return float(np.interp(percentile / 100.0, cum_wt, sorted_val))

if __name__ == "__main__":
    # Test query
    engine = QMAEngine()
    test_query = {
        "symbol": "HYPE",
        "fundingRate": -0.012,
        "marketCap": 8000000.0,
        "FDV": 60000000.0,
        "circRatio": 0.15,
        "fromATH": -92.0,
        "volume24h": 5200000.0
    }
    result = engine.analyze_signal(test_query)
    import json
    print(json.dumps(result, indent=2))
