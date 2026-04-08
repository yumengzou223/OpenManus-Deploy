"""
粒子群算法(PSO)最新改进技术示例代码
包含多种最新改进策略的实现
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple, Callable
import random

class AdaptivePSO:
    """自适应粒子群算法 - 包含多种最新改进技术"""
    
    def __init__(self, 
                 objective_func: Callable,
                 dim: int = 10,
                 pop_size: int = 30,
                 max_iter: int = 100,
                 bounds: Tuple[float, float] = (-10, 10)):
        """
        初始化自适应PSO算法
        
        参数:
            objective_func: 目标函数
            dim: 问题维度
            pop_size: 种群大小
            max_iter: 最大迭代次数
            bounds: 搜索边界
        """
        self.objective_func = objective_func
        self.dim = dim
        self.pop_size = pop_size
        self.max_iter = max_iter
        self.bounds = bounds
        
        # 自适应参数
        self.w_max = 0.9  # 最大惯性权重
        self.w_min = 0.4  # 最小惯性权重
        self.c1_max = 2.5  # 最大认知因子
        self.c1_min = 1.5  # 最小认知因子
        self.c2_max = 2.5  # 最大社会因子
        self.c2_min = 1.5  # 最小社会因子
        
        # 初始化种群
        self.positions = np.random.uniform(bounds[0], bounds[1], (pop_size, dim))
        self.velocities = np.random.uniform(-1, 1, (pop_size, dim))
        self.personal_best_positions = self.positions.copy()
        self.personal_best_values = np.full(pop_size, np.inf)
        
        # 全局最优
        self.global_best_position = None
        self.global_best_value = np.inf
        
        # 记录收敛过程
        self.convergence_history = []
        
    def adaptive_parameters(self, iteration: int) -> Tuple[float, float, float]:
        """
        自适应参数调整策略（最新研究改进）
        
        参数:
            iteration: 当前迭代次数
            
        返回:
            w: 惯性权重
            c1: 认知因子
            c2: 社会因子
        """
        # 非线性递减惯性权重
        w = self.w_max - (self.w_max - self.w_min) * (iteration / self.max_iter) ** 2
        
        # 基于迭代的自适应学习因子
        if iteration < self.max_iter * 0.3:
            # 初期：强调探索
            c1 = self.c1_max
            c2 = self.c1_min
        elif iteration < self.max_iter * 0.7:
            # 中期：平衡探索与开发
            c1 = (self.c1_max + self.c1_min) / 2
            c2 = (self.c2_max + self.c2_min) / 2
        else:
            # 后期：强调开发
            c1 = self.c1_min
            c2 = self.c2_max
            
        return w, c1, c2
    
    def chaotic_perturbation(self, position: np.ndarray) -> np.ndarray:
        """
        混沌扰动策略 - 避免早熟收敛
        
        参数:
            position: 粒子位置
            
        返回:
            扰动后的位置
        """
        # Logistic混沌映射
        chaos = 3.9 * position * (1 - position)
        perturbation = 0.1 * (chaos - 0.5)  # 小幅度扰动
        
        return position + perturbation
    
    def evaluate_population(self):
        """评估种群适应度"""
        for i in range(self.pop_size):
            # 计算适应度
            fitness = self.objective_func(self.positions[i])
            
            # 更新个体最优
            if fitness < self.personal_best_values[i]:
                self.personal_best_values[i] = fitness
                self.personal_best_positions[i] = self.positions[i].copy()
                
                # 更新全局最优
                if fitness < self.global_best_value:
                    self.global_best_value = fitness
                    self.global_best_position = self.positions[i].copy()
    
    def update_velocities_positions(self, iteration: int):
        """更新粒子速度和位置"""
        w, c1, c2 = self.adaptive_parameters(iteration)
        
        for i in range(self.pop_size):
            # 生成随机因子
            r1 = np.random.random(self.dim)
            r2 = np.random.random(self.dim)
            
            # 更新速度
            cognitive = c1 * r1 * (self.personal_best_positions[i] - self.positions[i])
            social = c2 * r2 * (self.global_best_position - self.positions[i])
            self.velocities[i] = w * self.velocities[i] + cognitive + social
            
            # 速度限制
            velocity_limit = 0.2 * (self.bounds[1] - self.bounds[0])
            self.velocities[i] = np.clip(self.velocities[i], -velocity_limit, velocity_limit)
            
            # 更新位置
            self.positions[i] += self.velocities[i]
            
            # 边界处理
            self.positions[i] = np.clip(self.positions[i], self.bounds[0], self.bounds[1])
            
            # 混沌扰动（以一定概率）
            if np.random.random() < 0.1:  # 10%概率进行混沌扰动
                self.positions[i] = self.chaotic_perturbation(self.positions[i])
    
    def optimize(self) -> Tuple[np.ndarray, float]:
        """执行优化过程"""
        print("开始自适应PSO优化...")
        
        for iteration in range(self.max_iter):
            # 评估种群
            self.evaluate_population()
            
            # 记录收敛历史
            self.convergence_history.append(self.global_best_value)
            
            # 更新速度和位置
            self.update_velocities_positions(iteration)
            
            # 打印进度
            if iteration % 20 == 0:
                print(f"迭代 {iteration:3d}/{self.max_iter}, 最优值: {self.global_best_value:.6f}")
        
        print(f"\n优化完成！")
        print(f"最终最优值: {self.global_best_value:.10f}")
        print(f"最优解: {self.global_best_position}")
        
        return self.global_best_position, self.global_best_value
    
    def plot_convergence(self):
        """绘制收敛曲线"""
        plt.figure(figsize=(10, 6))
        plt.plot(self.convergence_history, 'b-', linewidth=2)
        plt.xlabel('迭代次数', fontsize=12)
        plt.ylabel('最优适应度值', fontsize=12)
        plt.title('自适应PSO算法收敛曲线', fontsize=14)
        plt.grid(True, alpha=0.3)
        plt.yscale('log')
        plt.tight_layout()
        plt.show()


class HybridPSO_GA:
    """PSO-GA混合算法 - 结合遗传算法的交叉变异操作"""
    
    def __init__(self, objective_func: Callable, dim: int = 10, pop_size: int = 30):
        self.objective_func = objective_func
        self.dim = dim
        self.pop_size = pop_size
        
        # PSO参数
        self.w = 0.7
        self.c1 = 1.5
        self.c2 = 1.5
        
        # GA参数
        self.crossover_rate = 0.8
        self.mutation_rate = 0.1
        
        # 初始化
        self.positions = np.random.uniform(-10, 10, (pop_size, dim))
        self.velocities = np.random.uniform(-1, 1, (pop_size, dim))
        self.fitness = np.zeros(pop_size)
        
    def evaluate(self):
        """评估适应度"""
        for i in range(self.pop_size):
            self.fitness[i] = self.objective_func(self.positions[i])
    
    def pso_update(self):
        """PSO更新操作"""
        # 找到全局最优
        best_idx = np.argmin(self.fitness)
        global_best = self.positions[best_idx].copy()
        
        for i in range(self.pop_size):
            # 个体历史最优（简化版）
            personal_best = self.positions[i].copy()
            
            # 更新速度
            r1 = np.random.random(self.dim)
            r2 = np.random.random(self.dim)
            self.velocities[i] = (self.w * self.velocities[i] + 
                                 self.c1 * r1 * (personal_best - self.positions[i]) +
                                 self.c2 * r2 * (global_best - self.positions[i]))
            
            # 更新位置
            self.positions[i] += self.velocities[i]
    
    def ga_crossover(self):
        """遗传算法交叉操作"""
        # 选择父代（基于适应度）
        sorted_indices = np.argsort(self.fitness)
        parents = self.positions[sorted_indices[:self.pop_size//2]]
        
        # 执行交叉
        for i in range(0, len(parents)-1, 2):
            if np.random.random() < self.crossover_rate:
                # 单点交叉
                crossover_point = np.random.randint(1, self.dim-1)
                child1 = np.concatenate([parents[i][:crossover_point], 
                                        parents[i+1][crossover_point:]])
                child2 = np.concatenate([parents[i+1][:crossover_point], 
                                        parents[i][crossover_point:]])
                
                # 替换较差的个体
                worst_idx = sorted_indices[-(i//2 + 1)]
                self.positions[worst_idx] = child1
                
                if i//2 + 2 < self.pop_size:
                    worst_idx2 = sorted_indices[-(i//2 + 2)]
                    self.positions[worst_idx2] = child2
    
    def ga_mutation(self):
        """遗传算法变异操作"""
        for i in range(self.pop_size):
            if np.random.random() < self.mutation_rate:
                # 高斯变异
                mutation_strength = 0.1 * (np.random.random(self.dim) - 0.5)
                self.positions[i] += mutation_strength
    
    def optimize(self, max_iter: int = 100):
        """执行混合优化"""
        print("开始PSO-GA混合算法优化...")
        
        best_values = []
        
        for iteration in range(max_iter):
            # 评估
            self.evaluate()
            
            # 记录最优值
            best_fitness = np.min(self.fitness)
            best_values.append(best_fitness)
            
            # PSO更新
            self.pso_update()
            
            # GA操作
            self.ga_crossover()
            self.ga_mutation()
            
            if iteration % 20 == 0:
                print(f"迭代 {iteration:3d}/{max_iter}, 最优值: {best_fitness:.6f}")
        
        # 最终评估
        self.evaluate()
        best_idx = np.argmin(self.fitness)
        best_solution = self.positions[best_idx]
        best_value = self.fitness[best_idx]
        
        print(f"\n优化完成！")
        print(f"最终最优值: {best_value:.10f}")
        
        return best_solution, best_value, best_values


# 测试函数
def sphere_function(x):
    """Sphere测试函数 - 经典优化测试函数"""
    return np.sum(x**2)

def rastrigin_function(x):
    """Rastrigin测试函数 - 多模态优化测试函数"""
    A = 10
    return A * len(x) + np.sum(x**2 - A * np.cos(2 * np.pi * x))

def ackley_function(x):
    """Ackley测试函数 - 复杂多模态函数"""
    a = 20
    b = 0.2
    c = 2 * np.pi
    n = len(x)
    
    sum1 = np.sum(x**2)
    sum2 = np.sum(np.cos(c * x))
    
    term1 = -a * np.exp(-b * np.sqrt(sum1 / n))
    term2 = -np.exp(sum2 / n)
    
    return term1 + term2 + a + np.exp(1)


def main():
    """主函数 - 演示各种改进PSO算法"""
    print("=" * 60)
    print("粒子群算法(PSO)最新改进技术演示")
    print("=" * 60)
    
    # 测试1: 自适应PSO
    print("\n1. 自适应PSO算法测试 (Sphere函数)")
    print("-" * 40)
    
    adaptive_pso = AdaptivePSO(
        objective_func=sphere_function,
        dim=20,
        pop_size=40,
        max_iter=100,
        bounds=(-5.12, 5.12)
    )
    
    best_solution, best_value = adaptive_pso.optimize()
    adaptive_pso.plot_convergence()
    
    # 测试2: PSO-GA混合算法
    print("\n2. PSO-GA混合算法测试 (Rastrigin函数)")
    print("-" * 40)
    
    hybrid_pso_ga = HybridPSO_GA(
        objective_func=rastrigin_function,
        dim=10,
        pop_size=30
    )
    
    best_solution_ga, best_value_ga, convergence_ga = hybrid_pso_ga.optimize(max_iter=100)
    
    # 绘制混合算法收敛曲线
    plt.figure(figsize=(10, 6))
    plt.plot(convergence_ga, 'r-', linewidth=2)
    plt.xlabel('迭代次数', fontsize=12)
    plt.ylabel('最优适应度值', fontsize=12)
    plt.title('PSO-GA混合算法收敛曲线', fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.yscale('log')
    plt.tight_layout()
    plt.show()
    
    # 测试3: 不同测试函数比较
    print("\n3. 不同测试函数上的性能比较")
    print("-" * 40)
    
    test_functions = [
        ("Sphere", sphere_function),
        ("Rastrigin", rastrigin_function),
        ("Ackley", ackley_function)
    ]
    
    results = []
    
    for func_name, func in test_functions:
        print(f"\n测试函数: {func_name}")
        
        # 创建自适应PSO实例
        pso = AdaptivePSO(
            objective_func=func,
            dim=10,
            pop_size=30,
            max_iter=50,
            bounds=(-5.12, 5.12) if func_name != "Ackley" else (-32.768, 32.768)
        )
        
        _, best_val = pso.optimize()
        results.append((func_name, best_val))
    
    print("\n" + "=" * 60)
    print("性能比较结果:")
    print("-" * 60)
    for func_name, best_val in results:
        print(f"{func_name:15s}: 最优值 = {best_val:.10f}")
    
    print("\n" + "=" * 60)
    print("算法改进特点总结:")
    print("1. 自适应参数调整: 根据迭代进度动态调整惯性权重和学习因子")
    print("2. 混沌扰动策略: 引入混沌映射避免早熟收敛")
    print("3. 混合算法设计: 结合遗传算法的交叉变异操作")
    print("4. 边界处理优化: 智能边界约束和速度限制")
    print("=" * 60)


if __name__ == "__main__":
    main()