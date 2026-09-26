#!/usr/bin/env python3
"""
ML Prediction Engine for Huxley
Advanced predictive analytics for completion time, success probability, and resource needs
"""

import json
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import mean_absolute_error, accuracy_score, r2_score
import pickle
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MLPredictionEngine:
    """Advanced ML-based prediction engine for Huxley"""
    
    def __init__(self):
        self.catalyst_root = Path("{{CATALYST_ROOT}}")
        self.models_path = self.catalyst_root / "registry/ml_models"
        self.models_path.mkdir(parents=True, exist_ok=True)
        
        # Models
        self.completion_time_model = None
        self.success_probability_model = None
        self.resource_needs_model = None
        self.risk_assessment_model = None
        
        # Preprocessors
        self.scaler = StandardScaler()
        self.label_encoders = {}
        
        # Training data
        self.training_data = []
        self.model_metadata = {}
        
        # Load existing models if available
        self._load_models()
        
        # Initialize with synthetic data if no training data exists
        if not self.training_data:
            self._generate_synthetic_training_data()
            
        logger.info("ML Prediction Engine initialized")
    
    def _load_models(self):
        """Load existing trained models"""
        model_files = {
            'completion_time': self.models_path / 'completion_time_model.pkl',
            'success_probability': self.models_path / 'success_probability_model.pkl',
            'resource_needs': self.models_path / 'resource_needs_model.pkl',
            'risk_assessment': self.models_path / 'risk_assessment_model.pkl'
        }
        
        for model_name, model_path in model_files.items():
            if model_path.exists():
                try:
                    with open(model_path, 'rb') as f:
                        model_data = pickle.load(f)
                        setattr(self, f"{model_name}_model", model_data['model'])
                        if 'scaler' in model_data:
                            self.scaler = model_data['scaler']
                        if 'label_encoders' in model_data:
                            self.label_encoders.update(model_data['label_encoders'])
                    logger.info(f"Loaded {model_name} model")
                except Exception as e:
                    logger.warning(f"Failed to load {model_name} model: {e}")
    
    def _save_models(self):
        """Save trained models"""
        models_to_save = {
            'completion_time': self.completion_time_model,
            'success_probability': self.success_probability_model,
            'resource_needs': self.resource_needs_model,
            'risk_assessment': self.risk_assessment_model
        }
        
        for model_name, model in models_to_save.items():
            if model is not None:
                model_path = self.models_path / f'{model_name}_model.pkl'
                try:
                    model_data = {
                        'model': model,
                        'scaler': self.scaler,
                        'label_encoders': self.label_encoders,
                        'trained_at': datetime.now().isoformat(),
                        'metadata': self.model_metadata.get(model_name, {})
                    }
                    
                    with open(model_path, 'wb') as f:
                        pickle.dump(model_data, f)
                    logger.info(f"Saved {model_name} model")
                except Exception as e:
                    logger.error(f"Failed to save {model_name} model: {e}")
    
    def _generate_synthetic_training_data(self):
        """Generate synthetic training data based on Huxley patterns"""
        np.random.seed(42)  # For reproducible results
        
        # Define capsule types and their characteristics
        capsule_types = ['automation', 'web', 'ios', 'macos', 'backend', 'general']
        lanes = ['standard', 'standard']
        agents = ['automation-specialist', 'frontend-specialist', 'ios-specialist', 
                 'backend-architect', 'security-auditor', 'code-reviewer']
        
        # Generate 200 synthetic capsules
        for i in range(200):
            capsule_type = np.random.choice(capsule_types)
            lane = np.random.choice(lanes)
            
            # Type-specific characteristics
            base_complexity = {
                'automation': 3, 'web': 5, 'ios': 7, 'macos': 6, 'backend': 8, 'general': 4
            }[capsule_type]
            
            # Lane impact
            lane_multiplier = 1.5 if lane == 'standard' else 0.7
            
            # Features
            num_requirements = np.random.poisson(5) + 1
            num_dependencies = np.random.poisson(3)
            team_size = np.random.randint(1, 4)
            has_external_apis = np.random.choice([0, 1], p=[0.7, 0.3])
            has_database = np.random.choice([0, 1], p=[0.6, 0.4])
            complexity_score = base_complexity + num_requirements * 0.5 + num_dependencies * 0.3
            
            # Outcomes (what we want to predict)
            base_hours = complexity_score * lane_multiplier * (10 + np.random.normal(0, 3))
            completion_time = max(2, base_hours + np.random.normal(0, base_hours * 0.2))
            
            # Success probability based on complexity and team
            success_factors = 0.9 - (complexity_score / 20) + (team_size / 10) - (has_external_apis * 0.1)
            success_probability = max(0.1, min(0.99, success_factors + np.random.normal(0, 0.1)))
            actual_success = 1 if np.random.random() < success_probability else 0
            
            # Resource needs
            cpu_hours = completion_time * (1 + complexity_score / 10)
            memory_gb_hours = completion_time * (2 + num_dependencies)
            storage_gb = 1 + complexity_score + num_dependencies * 0.5
            
            # Risk factors
            risk_score = (complexity_score / 10) + (has_external_apis * 0.3) + (num_dependencies / 10)
            risk_level = 'high' if risk_score > 1.5 else 'medium' if risk_score > 0.8 else 'low'
            
            # Cost calculation (hypothetical)
            hourly_rate = 150  # $150/hour
            infrastructure_cost = cpu_hours * 0.10 + memory_gb_hours * 0.05 + storage_gb * 0.02
            total_cost = completion_time * hourly_rate + infrastructure_cost
            
            training_record = {
                # Features
                'capsule_type': capsule_type,
                'num_requirements': num_requirements,
                'num_dependencies': num_dependencies,
                'team_size': team_size,
                'has_external_apis': has_external_apis,
                'has_database': has_database,
                'complexity_score': complexity_score,
                'primary_agent': np.random.choice(agents),
                
                # Targets
                'completion_time_hours': completion_time,
                'success': actual_success,
                'cpu_hours': cpu_hours,
                'memory_gb_hours': memory_gb_hours,
                'storage_gb': storage_gb,
                'total_cost': total_cost,
                'risk_level': risk_level,
                
                # Metadata
                'created_at': (datetime.now() - timedelta(days=np.random.randint(1, 365))).isoformat(),
                'synthetic': True
            }
            
            self.training_data.append(training_record)
        
        logger.info(f"Generated {len(self.training_data)} synthetic training records")
    
    def add_real_data(self, capsule_data: Dict[str, Any]):
        """Add real capsule data to training set"""
        # Convert real capsule data to training format
        training_record = self._convert_capsule_to_training_record(capsule_data)
        self.training_data.append(training_record)
        
        # Retrain models with new data
        if len(self.training_data) > 10:  # Minimum data for training
            self._train_all_models()
        
        logger.info("Added real capsule data to training set")
    
    def _convert_capsule_to_training_record(self, capsule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert capsule data to training record format"""
        metadata = capsule_data.get('metadata', {})
        
        # Extract features
        record = {
            'capsule_type': metadata.get('type', 'general'),
            'num_requirements': len(metadata.get('requirements', [])),
            'num_dependencies': len(metadata.get('dependencies', [])),
            'team_size': len(metadata.get('assigned_agents', [])),
            'has_external_apis': 1 if 'api' in str(metadata).lower() else 0,
            'has_database': 1 if 'database' in str(metadata).lower() else 0,
            'complexity_score': metadata.get('complexity', {}).get('score', 5),
            'primary_agent': metadata.get('assigned_agents', ['general'])[0] if metadata.get('assigned_agents') else 'general',
            'synthetic': False
        }
        
        # Extract outcomes if available
        if 'duration_hours' in metadata:
            record['completion_time_hours'] = metadata['duration_hours']
        
        if 'success' in metadata:
            record['success'] = 1 if metadata['success'] else 0
        
        # Estimate resource usage from metrics
        metrics = capsule_data.get('metrics', {})
        if metrics:
            record['cpu_hours'] = metrics.get('cpu_usage', 0) * record.get('completion_time_hours', 8) / 100
            record['memory_gb_hours'] = metrics.get('memory_usage', 256) * record.get('completion_time_hours', 8) / 1024
        
        return record
    
    def _prepare_features(self, data: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Prepare features for ML training"""
        df = pd.DataFrame(data)
        
        # Encode categorical variables
        
        for col in categorical_columns:
            if col in df.columns:
                if col not in self.label_encoders:
                    self.label_encoders[col] = LabelEncoder()
                    df[f'{col}_encoded'] = self.label_encoders[col].fit_transform(df[col].fillna('unknown'))
                else:
                    # Handle new categories
                    df[f'{col}_encoded'] = df[col].apply(
                        lambda x: self._safe_encode(self.label_encoders[col], x)
                    )
        
        # Select feature columns
        feature_columns = [
            'num_requirements', 'num_dependencies', 'team_size', 'has_external_apis',
            'has_database', 'complexity_score', 'capsule_type_encoded', 'lane_encoded',
            'primary_agent_encoded'
        ]
        
        # Ensure all feature columns exist
        for col in feature_columns:
            if col not in df.columns:
                df[col] = 0
        
        X = df[feature_columns].fillna(0)
        
        targets = {}
        target_columns = ['completion_time_hours', 'success', 'cpu_hours', 'memory_gb_hours', 'storage_gb', 'total_cost']
        
        for target in target_columns:
            if target in df.columns:
                targets[target] = df[target].fillna(df[target].median() if target != 'success' else 0)
        
        return X, targets
    
    def _safe_encode(self, encoder, value):
        """Safely encode categorical value, handling unseen categories"""
        if pd.isna(value):
            value = 'unknown'
        
        try:
            return encoder.transform([str(value)])[0]
        except ValueError:
            # Unseen category, return most common class
            return encoder.transform([encoder.classes_[0]])[0]
    
    def _train_all_models(self):
        """Train all ML models"""
        if len(self.training_data) < 10:
            logger.warning("Insufficient training data")
            return
        
        logger.info("Training ML models...")
        
        # Prepare data
        X, targets = self._prepare_features(self.training_data)
        
        if X.empty:
            logger.error("No features available for training")
            return
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train completion time model
        if 'completion_time_hours' in targets:
            self._train_completion_time_model(X_scaled, targets['completion_time_hours'])
        
        # Train success probability model
        if 'success' in targets:
            self._train_success_model(X_scaled, targets['success'])
        
        # Train resource needs model
        resource_targets = ['cpu_hours', 'memory_gb_hours', 'storage_gb']
        available_resources = [t for t in resource_targets if t in targets]
        if available_resources:
            self._train_resource_model(X_scaled, {t: targets[t] for t in available_resources})
        
        # Save models
        self._save_models()
        
        logger.info("ML model training completed")
    
    def _train_completion_time_model(self, X: np.ndarray, y: pd.Series):
        """Train completion time prediction model"""
        if len(y) < 10:
            return
        
        # Try multiple models and select best
        models = {
            'random_forest': RandomForestRegressor(n_estimators=100, random_state=42),
            'linear': LinearRegression()
        }
        
        best_model = None
        best_score = float('-inf')
        
        for name, model in models.items():
            try:
                # Cross-validation
                scores = cross_val_score(model, X, y, cv=min(5, len(y)//2), scoring='r2')
                avg_score = scores.mean()
                
                if avg_score > best_score:
                    best_score = avg_score
                    best_model = model
                    
                logger.info(f"Completion time {name} model R² score: {avg_score:.3f}")
            except Exception as e:
                logger.warning(f"Failed to train {name} completion model: {e}")
        
        if best_model is not None:
            best_model.fit(X, y)
            self.completion_time_model = best_model
            self.model_metadata['completion_time'] = {
                'score': best_score,
                'training_samples': len(y),
                'features': X.shape[1]
            }
    
    def _train_success_model(self, X: np.ndarray, y: pd.Series):
        """Train success probability model"""
        if len(y) < 10 or y.nunique() < 2:
            return
        
        models = {
            'random_forest': RandomForestClassifier(n_estimators=100, random_state=42),
            'logistic': LogisticRegression(random_state=42)
        }
        
        best_model = None
        best_score = 0
        
        for name, model in models.items():
            try:
                scores = cross_val_score(model, X, y, cv=min(5, len(y)//2), scoring='accuracy')
                avg_score = scores.mean()
                
                if avg_score > best_score:
                    best_score = avg_score
                    best_model = model
                    
                logger.info(f"Success {name} model accuracy: {avg_score:.3f}")
            except Exception as e:
                logger.warning(f"Failed to train {name} success model: {e}")
        
        if best_model is not None:
            best_model.fit(X, y)
            self.success_probability_model = best_model
            self.model_metadata['success_probability'] = {
                'score': best_score,
                'training_samples': len(y),
                'features': X.shape[1]
            }
    
    def _train_resource_model(self, X: np.ndarray, targets: Dict[str, pd.Series]):
        """Train resource needs prediction model"""
        # Combine resource targets into a multi-output model
        y_combined = pd.DataFrame(targets)
        
        if len(y_combined) < 10:
            return
        
        # Use RandomForest for multi-output regression
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        
        try:
            model.fit(X, y_combined)
            self.resource_needs_model = model
            
            # Calculate scores for each target
            scores = {}
            for col in y_combined.columns:
                pred = model.predict(X)
                if pred.ndim > 1:
                    col_idx = list(y_combined.columns).index(col)
                    col_pred = pred[:, col_idx]
                else:
                    col_pred = pred
                
                score = r2_score(y_combined[col], col_pred)
                scores[col] = score
                logger.info(f"Resource {col} model R² score: {score:.3f}")
            
            self.model_metadata['resource_needs'] = {
                'scores': scores,
                'training_samples': len(y_combined),
                'features': X.shape[1]
            }
            
        except Exception as e:
            logger.error(f"Failed to train resource model: {e}")
    
    def predict_completion_time(self, capsule_features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict completion time for a capsule"""
        if self.completion_time_model is None:
            # Fallback to heuristic
            complexity = capsule_features.get('complexity_score', 5)
            estimated_hours = complexity * lane_multiplier * 8
            
            return {
                'predicted_hours': estimated_hours,
                'confidence': 0.3,  # Low confidence for heuristic
                'method': 'heuristic',
                'range': {
                    'min': estimated_hours * 0.7,
                    'max': estimated_hours * 1.5
                }
            }
        
        try:
            # Prepare features
            feature_data = [capsule_features]
            X, _ = self._prepare_features(feature_data)
            X_scaled = self.scaler.transform(X)
            
            # Predict
            prediction = self.completion_time_model.predict(X_scaled)[0]
            
            # Calculate confidence based on model type
            confidence = 0.8  # Default confidence
            if hasattr(self.completion_time_model, 'estimators_'):
                # Random Forest - can calculate prediction variance
                predictions = [tree.predict(X_scaled)[0] for tree in self.completion_time_model.estimators_]
                std = np.std(predictions)
                confidence = max(0.1, 1 - (std / prediction))
            
            return {
                'predicted_hours': max(1, prediction),
                'confidence': confidence,
                'method': 'ml_model',
                'model_score': self.model_metadata.get('completion_time', {}).get('score', 0),
                'range': {
                    'min': prediction * 0.8,
                    'max': prediction * 1.3
                }
            }
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return self.predict_completion_time(capsule_features)  # Fallback to heuristic
    
    def predict_success_probability(self, capsule_features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict success probability for a capsule"""
        if self.success_probability_model is None:
            # Fallback heuristic
            complexity = capsule_features.get('complexity_score', 5)
            team_size = capsule_features.get('team_size', 1)
            base_prob = 0.85 - (complexity / 20) + (team_size / 10)
            probability = max(0.1, min(0.95, base_prob))
            
            return {
                'success_probability': probability,
                'confidence': 0.3,
                'method': 'heuristic',
                'risk_factors': ['complexity_score', 'team_size']
            }
        
        try:
            # Prepare features
            feature_data = [capsule_features]
            X, _ = self._prepare_features(feature_data)
            X_scaled = self.scaler.transform(X)
            
            # Predict probability
            if hasattr(self.success_probability_model, 'predict_proba'):
                proba = self.success_probability_model.predict_proba(X_scaled)[0]
                success_prob = proba[1] if len(proba) > 1 else proba[0]
            else:
                success_prob = self.success_probability_model.predict(X_scaled)[0]
            
            # Identify risk factors
            risk_factors = []
            if capsule_features.get('complexity_score', 0) > 8:
                risk_factors.append('high_complexity')
            if capsule_features.get('num_dependencies', 0) > 5:
                risk_factors.append('many_dependencies')
            if capsule_features.get('has_external_apis', 0):
                risk_factors.append('external_apis')
            
            return {
                'success_probability': float(success_prob),
                'confidence': 0.8,
                'method': 'ml_model',
                'model_accuracy': self.model_metadata.get('success_probability', {}).get('score', 0),
                'risk_factors': risk_factors
            }
            
        except Exception as e:
            logger.error(f"Success prediction failed: {e}")
            return self.predict_success_probability(capsule_features)  # Fallback
    
    def predict_resource_needs(self, capsule_features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict resource requirements for a capsule"""
        if self.resource_needs_model is None:
            # Fallback heuristic
            complexity = capsule_features.get('complexity_score', 5)
            estimated_hours = capsule_features.get('predicted_hours', complexity * 8)
            
            return {
                'cpu_hours': estimated_hours * (1 + complexity / 10),
                'memory_gb_hours': estimated_hours * (2 + capsule_features.get('num_dependencies', 0)),
                'storage_gb': 1 + complexity + capsule_features.get('num_dependencies', 0) * 0.5,
                'confidence': 0.3,
                'method': 'heuristic'
            }
        
        try:
            # Prepare features
            feature_data = [capsule_features]
            X, _ = self._prepare_features(feature_data)
            X_scaled = self.scaler.transform(X)
            
            # Predict resources
            predictions = self.resource_needs_model.predict(X_scaled)[0]
            
            # Map predictions to resource types
            if hasattr(predictions, '__len__') and len(predictions) > 1:
                resources = {
                    'cpu_hours': max(0, predictions[0]),
                    'memory_gb_hours': max(0, predictions[1]),
                    'storage_gb': max(0.1, predictions[2] if len(predictions) > 2 else 1)
                }
            else:
                # Single output, estimate others
                cpu_hours = max(0, float(predictions))
                resources = {
                    'cpu_hours': cpu_hours,
                    'memory_gb_hours': cpu_hours * 2,
                    'storage_gb': max(0.1, cpu_hours / 10)
                }
            
            return {
                **resources,
                'confidence': 0.7,
                'method': 'ml_model',
                'model_scores': self.model_metadata.get('resource_needs', {}).get('scores', {})
            }
            
        except Exception as e:
            logger.error(f"Resource prediction failed: {e}")
            return self.predict_resource_needs(capsule_features)  # Fallback
    
    def predict_cost(self, capsule_features: Dict[str, Any], 
                    hourly_rate: float = 150.0) -> Dict[str, Any]:
        """Predict total cost for a capsule"""
        # Get time and resource predictions
        time_pred = self.predict_completion_time(capsule_features)
        resource_pred = self.predict_resource_needs(capsule_features)
        
        # Calculate costs
        development_cost = time_pred['predicted_hours'] * hourly_rate
        
        # Infrastructure costs (simplified)
        cpu_cost = resource_pred['cpu_hours'] * 0.10  # $0.10/CPU-hour
        memory_cost = resource_pred['memory_gb_hours'] * 0.05  # $0.05/GB-hour
        storage_cost = resource_pred['storage_gb'] * 0.02  # $0.02/GB
        
        infrastructure_cost = cpu_cost + memory_cost + storage_cost
        total_cost = development_cost + infrastructure_cost
        
        return {
            'total_cost': total_cost,
            'breakdown': {
                'development': development_cost,
                'infrastructure': infrastructure_cost,
                'cpu': cpu_cost,
                'memory': memory_cost,
                'storage': storage_cost
            },
            'confidence': min(time_pred['confidence'], resource_pred['confidence']),
            'range': {
                'min': total_cost * 0.8,
                'max': total_cost * 1.4
            }
        }
    
    def get_optimization_recommendations(self, capsule_features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get optimization recommendations based on predictions"""
        recommendations = []
        
        # Get predictions
        time_pred = self.predict_completion_time(capsule_features)
        success_pred = self.predict_success_probability(capsule_features)
        cost_pred = self.predict_cost(capsule_features)
        
        # Time optimization
        if time_pred['predicted_hours'] > 40:
            recommendations.append({
                'type': 'time_optimization',
                'priority': 'high',
                'suggestion': 'Consider breaking into smaller capsules',
                'impact': 'Could reduce time by 20-30%'
            })
        
        # Success optimization
        if success_pred['success_probability'] < 0.7:
            recommendations.append({
                'type': 'success_optimization',
                'priority': 'critical',
                'suggestion': 'Add more team members or reduce scope',
                'impact': f"Could improve success from {success_pred['success_probability']:.1%} to 85%+"
            })
        
        # Cost optimization
        if cost_pred['total_cost'] > 5000:
            recommendations.append({
                'type': 'cost_optimization',
                'priority': 'medium',
                'suggestion': 'Consider standard for rapid prototyping',
                'impact': f"Could save ${cost_pred['total_cost'] * 0.3:.0f}"
            })
        
        # Risk-based recommendations
        for risk_factor in success_pred.get('risk_factors', []):
            if risk_factor == 'high_complexity':
                recommendations.append({
                    'type': 'complexity_reduction',
                    'priority': 'high',
                    'suggestion': 'Simplify requirements or use proven patterns',
                    'impact': 'Reduce complexity and increase success probability'
                })
            elif risk_factor == 'external_apis':
                recommendations.append({
                    'type': 'api_risk_mitigation',
                    'priority': 'medium',
                    'suggestion': 'Plan for API failures and have backup strategies',
                    'impact': 'Reduce external dependency risks'
                })
        
        return recommendations
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get status of all ML models"""
        status = {
            'models_trained': 0,
            'training_data_size': len(self.training_data),
            'last_training': None,
            'model_details': {}
        }
        
        models = ['completion_time', 'success_probability', 'resource_needs']
        
        for model_name in models:
            model = getattr(self, f'{model_name}_model', None)
            if model is not None:
                status['models_trained'] += 1
                status['model_details'][model_name] = self.model_metadata.get(model_name, {})
        
        return status


def main():
    """CLI interface for ML prediction engine"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ML Prediction Engine")
    parser.add_argument("command", choices=["train", "predict", "status", "test"],
                       help="Command to execute")
    parser.add_argument("--capsule-type", default="general", help="Capsule type")
    parser.add_argument("--lane", default="standard", help="Lane")
    parser.add_argument("--complexity", type=int, default=5, help="Complexity score")
    
    args = parser.parse_args()
    
    engine = MLPredictionEngine()
    
    if args.command == "train":
        engine._train_all_models()
        print("Training completed")
    
    elif args.command == "predict":
        features = {
            'capsule_type': args.capsule_type,
            'complexity_score': args.complexity,
            'num_requirements': 5,
            'num_dependencies': 2,
            'team_size': 1,
            'has_external_apis': 0,
            'has_database': 0
        }
        
        time_pred = engine.predict_completion_time(features)
        success_pred = engine.predict_success_probability(features)
        cost_pred = engine.predict_cost(features)
        
        print("PREDICTIONS:")
        print(f"Completion Time: {time_pred['predicted_hours']:.1f} hours (confidence: {time_pred['confidence']:.2f})")
        print(f"Success Probability: {success_pred['success_probability']:.1%} (confidence: {success_pred['confidence']:.2f})")
        print(f"Estimated Cost: ${cost_pred['total_cost']:.2f}")
        
        recommendations = engine.get_optimization_recommendations(features)
        if recommendations:
            print("\nRECOMMENDATIONS:")
            for rec in recommendations:
                print(f"- {rec['suggestion']} (Priority: {rec['priority']})")
    
    elif args.command == "status":
        status = engine.get_model_status()
        print(json.dumps(status, indent=2))
    
    elif args.command == "test":
        # Test with various scenarios
        test_cases = [
        ]
        
        print("TEST PREDICTIONS:")
        for i, case in enumerate(test_cases, 1):
            case.update({
                'num_requirements': 5, 'num_dependencies': 2, 'team_size': 1,
                'has_external_apis': 0, 'has_database': 0
            })
            
            time_pred = engine.predict_completion_time(case)
            success_pred = engine.predict_success_probability(case)
            
            print(f"  Time: {time_pred['predicted_hours']:.1f}h, Success: {success_pred['success_probability']:.1%}")


if __name__ == "__main__":
    main()