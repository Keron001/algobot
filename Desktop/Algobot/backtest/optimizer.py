import numpy as np
import pandas as pd
from itertools import product
from utils.logger import get_logger
from .backtester import Backtester

logger = get_logger("Optimizer")

class Optimizer:
    def __init__(self, strategy_class, data, param_grid, optimization_metric='sharpe_ratio'):
        self.strategy_class = strategy_class
        self.data = data
        self.param_grid = param_grid
        self.optimization_metric = optimization_metric
        self.results = []
        
    def grid_search(self, min_trades=10):
        """Perform grid search optimization"""
        logger.info(f"Starting grid search with {len(list(product(*self.param_grid.values())))} combinations")
        
        best_score = -np.inf
        best_params = None
        best_performance = None
        
        # Generate all parameter combinations
        param_combinations = list(product(*self.param_grid.values()))
        
        for i, params in enumerate(param_combinations):
            param_dict = dict(zip(self.param_grid.keys(), params))
            
            # Skip invalid combinations
            if not self._is_valid_combination(param_dict):
                continue
                
            try:
                # Run backtest
                backtester = Backtester(self.strategy_class, self.data)
                performance = backtester.run(**param_dict)
                
                # Check minimum trades requirement
                if performance['num_trades'] < min_trades:
                    continue
                
                # Get optimization score
                score = performance.get(self.optimization_metric, -np.inf)
                
                # Store results
                result = {
                    'params': param_dict.copy(),
                    'performance': performance,
                    'score': score
                }
                self.results.append(result)
                
                # Update best if better
                if score > best_score:
                    best_score = score
                    best_params = param_dict.copy()
                    best_performance = performance
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(param_combinations)} combinations")
                    
            except Exception as e:
                logger.error(f"Error testing params {param_dict}: {e}")
                continue
        
        logger.info(f"Grid search completed. Best score: {best_score:.4f}")
        logger.info(f"Best parameters: {best_params}")
        
        return best_params, best_performance, self.results
    
    def walk_forward_analysis(self, train_days=252, test_days=63, step_days=21):
        """Perform walk-forward analysis"""
        logger.info("Starting walk-forward analysis")
        
        results = []
        total_days = len(self.data)
        
        for start_idx in range(0, total_days - train_days - test_days, step_days):
            # Define train and test periods
            train_end = start_idx + train_days
            test_end = train_end + test_days
            
            if test_end > total_days:
                break
                
            train_data = self.data.iloc[start_idx:train_end]
            test_data = self.data.iloc[train_end:test_end]
            
            # Optimize on training data
            best_params, _, _ = self.grid_search()
            
            if best_params is None:
                continue
                
            # Test on out-of-sample data
            backtester = Backtester(self.strategy_class, test_data)
            performance = backtester.run(**best_params)
            
            results.append({
                'train_start': start_idx,
                'train_end': train_end,
                'test_start': train_end,
                'test_end': test_end,
                'params': best_params,
                'performance': performance
            })
            
            logger.info(f"Walk-forward period {len(results)}: {performance['total_return']:.2%} return")
        
        return results
    
    def _is_valid_combination(self, params):
        """Check if parameter combination is valid"""
        # For moving average strategy, ensure short window < long window
        if 'short_window' in params and 'long_window' in params:
            if params['short_window'] >= params['long_window']:
                return False
        
        # Add other validation rules as needed
        return True
    
    def get_top_results(self, n=10):
        """Get top N results sorted by optimization metric"""
        if not self.results:
            return []
        
        sorted_results = sorted(self.results, key=lambda x: x['score'], reverse=True)
        return sorted_results[:n]
    
    def plot_optimization_results(self):
        """Plot optimization results (placeholder for visualization)"""
        if not self.results:
            logger.warning("No results to plot")
            return
        
        # This would create visualizations of the optimization results
        # You can implement matplotlib/plotly visualizations here
        logger.info(f"Optimization results: {len(self.results)} combinations tested")
        
        # Print top results
        top_results = self.get_top_results(5)
        logger.info("Top 5 results:")
        for i, result in enumerate(top_results):
            logger.info(f"{i+1}. Score: {result['score']:.4f}, Params: {result['params']}")

class MultiTimeframeOptimizer:
    """Optimizer for multiple timeframes"""
    
    def __init__(self, strategy_class, data_dict, param_grid):
        self.strategy_class = strategy_class
        self.data_dict = data_dict  # {timeframe: data}
        self.param_grid = param_grid
        self.results = {}
        
    def optimize_all_timeframes(self):
        """Optimize parameters for all timeframes"""
        for timeframe, data in self.data_dict.items():
            logger.info(f"Optimizing for timeframe: {timeframe}")
            optimizer = Optimizer(self.strategy_class, data, self.param_grid)
            best_params, best_performance, all_results = optimizer.grid_search()
            
            self.results[timeframe] = {
                'best_params': best_params,
                'best_performance': best_performance,
                'all_results': all_results
            }
        
        return self.results 

class PortfolioOptimizer:
    """Optimize parameters across multiple symbols (portfolio-level)."""
    def __init__(self, strategy_class, data_dict, param_grid, optimization_metric='sharpe_ratio'):
        self.strategy_class = strategy_class
        self.data_dict = data_dict  # {symbol: DataFrame}
        self.param_grid = param_grid
        self.optimization_metric = optimization_metric
        self.results = []

    def grid_search(self, min_trades=10):
        from itertools import product
        import copy
        logger.info(f"Starting portfolio grid search with {len(self.data_dict)} symbols and {len(list(product(*self.param_grid.values())))} param sets")
        best_score = -np.inf
        best_params = None
        best_performance = None
        param_combinations = list(product(*self.param_grid.values()))
        for i, params in enumerate(param_combinations):
            param_dict = dict(zip(self.param_grid.keys(), params))
            portfolio_performance = {'total_return': 0, 'sharpe_ratio': 0, 'num_trades': 0, 'final_balance': 0}
            all_trades = []
            valid = True
            for symbol, data in self.data_dict.items():
                try:
                    backtester = Backtester(self.strategy_class, data)
                    perf = backtester.run(**param_dict)
                    if perf['num_trades'] < min_trades:
                        valid = False
                        break
                    portfolio_performance['total_return'] += perf['total_return']
                    portfolio_performance['sharpe_ratio'] += perf['sharpe_ratio']
                    portfolio_performance['num_trades'] += perf['num_trades']
                    portfolio_performance['final_balance'] += perf['final_balance']
                    if isinstance(perf['trades'], list):
                        all_trades.extend(perf['trades'])
                except Exception as e:
                    logger.error(f"Error for symbol {symbol} with params {param_dict}: {e}")
                    valid = False
                    break
            if not valid:
                continue
            # Average metrics across symbols
            n = len(self.data_dict)
            for k in ['total_return', 'sharpe_ratio', 'final_balance']:
                portfolio_performance[k] /= n
            result = {
                'params': copy.deepcopy(param_dict),
                'performance': portfolio_performance,
                'score': portfolio_performance[self.optimization_metric],
                'trades': all_trades
            }
            self.results.append(result)
            if result['score'] > best_score:
                best_score = result['score']
                best_params = copy.deepcopy(param_dict)
                best_performance = portfolio_performance
            if (i + 1) % 10 == 0:
                logger.info(f"Processed {i + 1}/{len(param_combinations)} param sets")
        logger.info(f"Portfolio grid search completed. Best score: {best_score:.4f}")
        logger.info(f"Best parameters: {best_params}")
        return best_params, best_performance, self.results

    def get_top_results(self, n=10):
        if not self.results:
            return []
        sorted_results = sorted(self.results, key=lambda x: x['score'], reverse=True)
        return sorted_results[:n]

    def plot_param_surface(self, x_param, y_param, metric='sharpe_ratio'):
        """Plot a heatmap of parameter performance (requires 2D grid)."""
        import matplotlib.pyplot as plt
        import numpy as np
        xs = sorted(set(r['params'][x_param] for r in self.results))
        ys = sorted(set(r['params'][y_param] for r in self.results))
        z = np.zeros((len(xs), len(ys)), dtype=float)
        for r in self.results:
            xi = xs.index(r['params'][x_param])
            yi = ys.index(r['params'][y_param])
            z[xi, yi] = float(r['performance'][metric]) if metric in r['performance'] else float(r['score'])
        plt.figure(figsize=(8, 6))
        plt.imshow(z, origin='lower', aspect='auto', extent=(min(ys), max(ys), min(xs), max(xs)))
        plt.colorbar(label=metric)
        plt.xlabel(y_param)
        plt.ylabel(x_param)
        plt.title(f'{metric} surface')
        plt.tight_layout()
        plt.savefig(f'{metric}_surface.png')
        plt.close()
        logger.info(f"Parameter surface plot saved as {metric}_surface.png") 