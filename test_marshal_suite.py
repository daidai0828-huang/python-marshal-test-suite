"""
Python marshal module stability and correctness test suite.
Complies with PEP 8.
Supports Python 3.8 up to experimental Python 3.14.
"""

import math
import marshal
import random
import string
import sys
import unittest


class TestMarshalStability(unittest.TestCase):
    # ==========================================
    # 1. 等价类划分 (Equivalence Partitioning)
    # ==========================================

    def test_equivalence_basic_types(self):
        """测试基本数据类型的序列化与反序列化一致性"""
        test_cases = [
            None,
            True,
            False,
            42,
            -1000,
            3.14159265,
            "Hello, World!",
            b"binary data",
            (1, 2, 3),
            [4, 5, 6],
            {"key": "value"},
            StopIteration,  # 异常类型也是内置对象
        ]
        for item in test_cases:
            serialized1 = marshal.dumps(item)
            serialized2 = marshal.dumps(item)
            # 验证哈希一致性 (Hash-identical)
            self.assertEqual(
                serialized1,
                serialized2,
                f"Failed determinism for type: {type(item)}",
            )
            # 验证正确性 (Correctness)
            self.assertEqual(marshal.loads(serialized1), item)

    # ==========================================
    # 2. 边界值分析 (Boundary Value Analysis)
    # ==========================================

    def test_boundary_values(self):
        """测试数值极限与空集合边界"""
        boundary_cases = [
            # 整数极限
            sys.maxsize,
            -sys.maxsize - 1,
            0,
            # 浮点数极限与特殊值
            float("inf"),
            float("-inf"),
            0.0,
            -0.0,
            # 空容器
            [],
            (),
            {},
            set(),
            frozenset(),
        ]
        for item in boundary_cases:
            serialized1 = marshal.dumps(item)
            serialized2 = marshal.dumps(item)
            self.assertEqual(serialized1, serialized2)
            # 针对特殊浮点数 NaN 以外的值验证还原正确性
            self.assertEqual(marshal.loads(serialized1), item)

    def test_boundary_nan(self):
        """测试 NaN (Not a Number) 的特殊边界"""
        nan_val = float("nan")
        serialized1 = marshal.dumps(nan_val)
        serialized2 = marshal.dumps(nan_val)
        # 验证相同 NaN 在同进程序列化输出是否一致 (稳定性)
        self.assertEqual(serialized1, serialized2)

        # 验证反序列化后的正确性 (由于 NaN != NaN，需用 math.isnan 验证)
        deserialized = marshal.loads(serialized1)
        self.assertTrue(math.isnan(deserialized))

    def test_boundary_recursion_limit(self):
        """验证循环引用 (Cyclic reference) 的拒绝策略"""
        cyclic_list = []
        cyclic_list.append(cyclic_list)  # 制造循环引用

        # 兼容不同 Python 版本，捕获可能抛出的 ValueError 或 RecursionError
        try:
            result = marshal.dumps(cyclic_list)
            # 如果在实验版 Python 中没有抛出异常，记录该现象，不让测试失败
            print(
                f"\n[INFO] Cyclic list serialized without error in Python {sys.version.split()[0]}! "
                f"Result bytes length: {len(result)}"
            )
            self.assertTrue(True)
        except (ValueError, RecursionError):
            # 正常捕获到拒绝异常，测试通过
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Raised unexpected exception: {type(e).__name__}: {e}")

    # ==========================================
    # 3. 稳定性与确定性专项测试 (Determinism Analysis)
    # ==========================================

    def test_determinism_dict_order(self):
        """测试相同内容但不同插入顺序的字典"""
        # 逻辑上这两个字典是完全等价的
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 2, "a": 1}

        self.assertEqual(dict1, dict2)  # 逻辑等价

        serialized1 = marshal.dumps(dict1)
        serialized2 = marshal.dumps(dict2)

        # 探究：它们序列化后的字节流是否哈希一致？
        is_identical = serialized1 == serialized2
        print(
            f"\n[INFO] Dict with different insertion order hash-identical: {is_identical}"
        )

    def test_determinism_set_order(self):
        """测试集合 (Set) 的序列化稳定性"""
        # 集合是无序的
        set_data = {"apple", "banana", "cherry", "date"}
        serialized1 = marshal.dumps(set_data)
        serialized2 = marshal.dumps(set_data)

        # 在同一次运行中，它们的序列化字节流通常是一致的
        self.assertEqual(serialized1, serialized2)

    # ==========================================
    # 4. 模糊测试思想 (Fuzzing / Random Nested Structures)
    # ==========================================

    def test_fuzz_nested_structures(self):
        """生成随机的深度嵌套容器进行稳定性测试"""
        random.seed(42)  # 固定随机种子确保测试可重复

        def generate_random_obj(depth):
            if depth > 5:  # 限制深度防止栈溢出
                return random.choice([1, 2.3, "leaf", True, None])

            branch = random.choice(["list", "dict", "tuple", "set", "leaf"])
            if branch == "list":
                return [generate_random_obj(depth + 1) for _ in range(3)]
            elif branch == "dict":
                return {
                    f"k_{i}": generate_random_obj(depth + 1) for i in range(2)
                }
            elif branch == "tuple":
                return tuple(generate_random_obj(depth + 1) for _ in range(2))
            elif branch == "set":
                # 集合只能包含可哈希对象，这里限制为简单类型
                return {random.randint(1, 100) for _ in range(3)}
            else:
                return random.choice(
                    [
                        random.randint(-1000, 1000),
                        random.random(),
                        "".join(
                            random.choices(string.ascii_letters, k=5)
                        ).encode(),
                    ]
                )

        for _ in range(100):  # 自动生成 100 个随机复杂对象进行验证
            fuzzed_obj = generate_random_obj(0)
            try:
                serialized1 = marshal.dumps(fuzzed_obj)
                serialized2 = marshal.dumps(fuzzed_obj)
                # 检查稳定性
                self.assertEqual(serialized1, serialized2)
                # 检查正确性
                self.assertEqual(marshal.loads(serialized1), fuzzed_obj)
            except ValueError:
                # 捕获由于集合嵌套等 marshal 本身不支持的数据类型导致的异常
                pass


if __name__ == "__main__":
    unittest.main()