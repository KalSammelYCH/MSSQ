# Actual bilingual four-task example

This supplement presents one evaluated bijective-matching instance in Chinese and English. Each of the eight prompts below was issued independently; a model did not receive this combined document or the Gold records.

The example is the first contingent quartet in the matching family when sorted by its identifier. It was selected for presentation without consulting model scores. The original identifier is `bijective_matching__development__sequential_richer_balanced_002__contingent__quartet`.

## Reading the example

Sixteen entities must be assigned bijectively to sixteen values, subject to allowed domains and the listed constraints. The proposition is **P15 uses V11**. MUST asks whether every legal assignment satisfies it; MAY asks whether at least one does. WIT requests a legal assignment satisfying the proposition, and CEX requests one violating it.

The stored solution set contains 12 assignments: six satisfy the proposition and six violate it. Thus the Gold judgments are MUST = NO and MAY = YES; both construction requests have a legal answer. These counts and the records below are evaluator information, separate from the model-visible prompts.

[Chinese formal record](formal_records/zh.json) · [English formal record](formal_records/en.json) · [Semantic checking](semantic_check.md) · [Prompt identities and hashes](prompt_index.json)

The formal JSON files contain the selected CSP and quartet records, including all stored solutions and example Gold constructions. Original record fields are preserved. The prompts do not explicitly state that the CSP is guaranteed satisfiable; satisfiability is established by the stored solution set.

中文导读：这是实际评测题，不是为解释方法新编的例子。以下八份提示各自独立发送。形式记录中的12个解、正负侧各6个解及Gold答案属于评测信息，没有作为本说明的一部分发送给模型。

## MUST · zh

[Original prompt](prompts/bijective_matching/zh/p099.md) · SHA-256: `1f86bc6c9a79ff0644bd420dc4ea999528e28a79ea47d2ea17389180cf024347`

```text
# MUST

## 场景
共有16个实体P01到P16，以及16个有标签匹配值V01到V16。每个实体必须从自己的允许列表中选择恰好一个值；每个值也必须恰好使用一次。

## 实体及允许匹配值
[P01] V01, V10, V07, V08
[P02] V15, V14, V05, V08
[P03] V01, V03, V10, V02
[P04] V16, V05, V07, V11
[P05] V13, V07, V12, V05
[P06] V01, V07, V16, V15
[P07] V09, V01, V05, V13
[P08] V14, V08, V09, V06
[P09] V11, V06, V10, V13
[P10] V04, V11, V09, V12
[P11] V02, V15, V04, V09
[P12] V15, V14, V06, V02
[P13] V12, V16, V04, V06
[P14] V10, V02, V03, V16
[P15] V12, V11, V03, V14
[P16] V04, V03, V08, V13

## 计数组
[G1] P01, P02, P06, P07, P08, P09, P10, P12, P14, P16
[G2] P01, P02, P03, P04, P07, P08, P11, P15
[G3] P01, P04, P07, P10, P12, P13, P14, P15
[G4] P01, P02, P03, P04, P08, P13, P14
[G5] P01, P05, P09, P10, P11, P13
[G6] P01, P02, P03, P06, P09, P11, P12, P13, P15
[G7] P01, P07, P08, P11, P13, P16
[G8] P03, P04, P06, P07, P08, P09, P11, P14, P16
[SG01] P04, P05, P06, P09, P11, P13, P15, P16
[SG02] P01, P09, P10, P11, P13, P14
[H1] V01, V02, V03, V04, V06, V07, V08, V11, V16
[H2] V01, V05, V08, V09, V10, V11, V12, V13
[H3] V02, V05, V08, V09, V11, V14, V16
[H4] V01, V03, V07, V09, V11, V12, V14, V15, V16
[H5] V01, V06, V07, V11, V14, V15
[H6] V01, V03, V04, V06, V08, V09, V12, V13, V15
[H7] V01, V05, V09, V10, V13, V14
[H8] V01, V04, V06, V07, V08, V13, V15, V16
[SH01] V02, V10, V14, V16
[SH01C] V01, V03, V04, V05, V06, V07, V08, V09, V11, V12, V13, V15
[SH02] V01, V07, V08, V09, V12, V13, V14, V16
[SH02C] V02, V03, V04, V05, V06, V10, V11, V15

记 N(G,H) 为实体组 G 中最终取值属于值组 H 的实体数。

## 公开线索
[C01] P01=V08 与 P14=V03 要么同时成立，要么同时不成立。
[C02] P14=V03 与 P12=V15 要么同时成立，要么同时不成立。
[C03] P12=V15 与 P07=V09 要么同时成立，要么同时不成立。
[C04] P07=V09 与 P02=V14 要么同时成立，要么同时不成立。
[C05] N(G7,H7)+N(G5,H5)+N(G6,H1) = N(G7,H2)+N(G5,H8)+N(G3,H3)-2.
[C06] N(G2,H8)+N(G5,H1) = N(G5,H4)+N(G4,H1)-1.
[C07] N(G2,H5)+N(G5,H4) = N(G2,H8)+N(G5,H5)+2.
[C08] N(G1,H3)+N(G7,H8)+N(G6,H2) = N(G8,H1)+N(G8,H4)+N(G1,H5)-3.
[C09] N(G5,H3)+N(G6,H1) = N(G3,H3)+N(G4,H1)-2.
[S01] N(SG01,SH01) = N(SG01,SH01C)-4.
[S02] N(SG02,SH02) = N(SG02,SH02C).

## 目标命题
实体 P15 使用匹配值 V11。

## 输出要求
若目标命题在每个合法完整赋值中都成立，只输出 YES；否则只输出 NO。不要给出理由或其他文字。
```

## MUST · en

[Original prompt](prompts/bijective_matching/en/p003.md) · SHA-256: `2cd55ccd2b86e550153132934d1db7235ec43eb82e94cdd3d08a0c2f1930c760`

```text
# MUST

## Scenario
There are 16 entities P01 through P16 and 16 labeled matching values V01 through V16. Each entity must use exactly one value from its allowed list, and every value must be used exactly once.

## Entities and allowed matching values
[P01] V01, V10, V07, V08
[P02] V15, V14, V05, V08
[P03] V01, V03, V10, V02
[P04] V16, V05, V07, V11
[P05] V13, V07, V12, V05
[P06] V01, V07, V16, V15
[P07] V09, V01, V05, V13
[P08] V14, V08, V09, V06
[P09] V11, V06, V10, V13
[P10] V04, V11, V09, V12
[P11] V02, V15, V04, V09
[P12] V15, V14, V06, V02
[P13] V12, V16, V04, V06
[P14] V10, V02, V03, V16
[P15] V12, V11, V03, V14
[P16] V04, V03, V08, V13

## Counting groups
[G1] P01, P02, P06, P07, P08, P09, P10, P12, P14, P16
[G2] P01, P02, P03, P04, P07, P08, P11, P15
[G3] P01, P04, P07, P10, P12, P13, P14, P15
[G4] P01, P02, P03, P04, P08, P13, P14
[G5] P01, P05, P09, P10, P11, P13
[G6] P01, P02, P03, P06, P09, P11, P12, P13, P15
[G7] P01, P07, P08, P11, P13, P16
[G8] P03, P04, P06, P07, P08, P09, P11, P14, P16
[SG01] P04, P05, P06, P09, P11, P13, P15, P16
[SG02] P01, P09, P10, P11, P13, P14
[H1] V01, V02, V03, V04, V06, V07, V08, V11, V16
[H2] V01, V05, V08, V09, V10, V11, V12, V13
[H3] V02, V05, V08, V09, V11, V14, V16
[H4] V01, V03, V07, V09, V11, V12, V14, V15, V16
[H5] V01, V06, V07, V11, V14, V15
[H6] V01, V03, V04, V06, V08, V09, V12, V13, V15
[H7] V01, V05, V09, V10, V13, V14
[H8] V01, V04, V06, V07, V08, V13, V15, V16
[SH01] V02, V10, V14, V16
[SH01C] V01, V03, V04, V05, V06, V07, V08, V09, V11, V12, V13, V15
[SH02] V01, V07, V08, V09, V12, V13, V14, V16
[SH02C] V02, V03, V04, V05, V06, V10, V11, V15

Let N(G,H) be the number of entities in entity group G whose assigned value belongs to value group H.

## Public clues
[C01] P01=V08 holds if and only if P14=V03 holds.
[C02] P14=V03 holds if and only if P12=V15 holds.
[C03] P12=V15 holds if and only if P07=V09 holds.
[C04] P07=V09 holds if and only if P02=V14 holds.
[C05] N(G7,H7)+N(G5,H5)+N(G6,H1) = N(G7,H2)+N(G5,H8)+N(G3,H3)-2.
[C06] N(G2,H8)+N(G5,H1) = N(G5,H4)+N(G4,H1)-1.
[C07] N(G2,H5)+N(G5,H4) = N(G2,H8)+N(G5,H5)+2.
[C08] N(G1,H3)+N(G7,H8)+N(G6,H2) = N(G8,H1)+N(G8,H4)+N(G1,H5)-3.
[C09] N(G5,H3)+N(G6,H1) = N(G3,H3)+N(G4,H1)-2.
[S01] N(SG01,SH01) = N(SG01,SH01C)-4.
[S02] N(SG02,SH02) = N(SG02,SH02C).

## Target proposition
Entity P15 uses matching value V11.

## Output
If the target proposition holds in every valid complete assignment, output only YES; otherwise output only NO. Do not provide a rationale or other text.
```

## MAY · zh

[Original prompt](prompts/bijective_matching/zh/p098.md) · SHA-256: `0d317afb48fa426bf1b7c469c6f8ccc3f22ffe6894ecd130e253d04a0d7e846c`

```text
# MAY

## 场景
共有16个实体P01到P16，以及16个有标签匹配值V01到V16。每个实体必须从自己的允许列表中选择恰好一个值；每个值也必须恰好使用一次。

## 实体及允许匹配值
[P01] V01, V10, V07, V08
[P02] V15, V14, V05, V08
[P03] V01, V03, V10, V02
[P04] V16, V05, V07, V11
[P05] V13, V07, V12, V05
[P06] V01, V07, V16, V15
[P07] V09, V01, V05, V13
[P08] V14, V08, V09, V06
[P09] V11, V06, V10, V13
[P10] V04, V11, V09, V12
[P11] V02, V15, V04, V09
[P12] V15, V14, V06, V02
[P13] V12, V16, V04, V06
[P14] V10, V02, V03, V16
[P15] V12, V11, V03, V14
[P16] V04, V03, V08, V13

## 计数组
[G1] P01, P02, P06, P07, P08, P09, P10, P12, P14, P16
[G2] P01, P02, P03, P04, P07, P08, P11, P15
[G3] P01, P04, P07, P10, P12, P13, P14, P15
[G4] P01, P02, P03, P04, P08, P13, P14
[G5] P01, P05, P09, P10, P11, P13
[G6] P01, P02, P03, P06, P09, P11, P12, P13, P15
[G7] P01, P07, P08, P11, P13, P16
[G8] P03, P04, P06, P07, P08, P09, P11, P14, P16
[SG01] P04, P05, P06, P09, P11, P13, P15, P16
[SG02] P01, P09, P10, P11, P13, P14
[H1] V01, V02, V03, V04, V06, V07, V08, V11, V16
[H2] V01, V05, V08, V09, V10, V11, V12, V13
[H3] V02, V05, V08, V09, V11, V14, V16
[H4] V01, V03, V07, V09, V11, V12, V14, V15, V16
[H5] V01, V06, V07, V11, V14, V15
[H6] V01, V03, V04, V06, V08, V09, V12, V13, V15
[H7] V01, V05, V09, V10, V13, V14
[H8] V01, V04, V06, V07, V08, V13, V15, V16
[SH01] V02, V10, V14, V16
[SH01C] V01, V03, V04, V05, V06, V07, V08, V09, V11, V12, V13, V15
[SH02] V01, V07, V08, V09, V12, V13, V14, V16
[SH02C] V02, V03, V04, V05, V06, V10, V11, V15

记 N(G,H) 为实体组 G 中最终取值属于值组 H 的实体数。

## 公开线索
[C01] P01=V08 与 P14=V03 要么同时成立，要么同时不成立。
[C02] P14=V03 与 P12=V15 要么同时成立，要么同时不成立。
[C03] P12=V15 与 P07=V09 要么同时成立，要么同时不成立。
[C04] P07=V09 与 P02=V14 要么同时成立，要么同时不成立。
[C05] N(G7,H7)+N(G5,H5)+N(G6,H1) = N(G7,H2)+N(G5,H8)+N(G3,H3)-2.
[C06] N(G2,H8)+N(G5,H1) = N(G5,H4)+N(G4,H1)-1.
[C07] N(G2,H5)+N(G5,H4) = N(G2,H8)+N(G5,H5)+2.
[C08] N(G1,H3)+N(G7,H8)+N(G6,H2) = N(G8,H1)+N(G8,H4)+N(G1,H5)-3.
[C09] N(G5,H3)+N(G6,H1) = N(G3,H3)+N(G4,H1)-2.
[S01] N(SG01,SH01) = N(SG01,SH01C)-4.
[S02] N(SG02,SH02) = N(SG02,SH02C).

## 目标命题
实体 P15 使用匹配值 V11。

## 输出要求
若目标命题在至少一个合法完整赋值中成立，只输出 YES；否则只输出 NO。不要给出理由或其他文字。
```

## MAY · en

[Original prompt](prompts/bijective_matching/en/p002.md) · SHA-256: `d98d3c483f72c735b0e99f2e09cefdca8ab2a4a154b918272c041d754869b63c`

```text
# MAY

## Scenario
There are 16 entities P01 through P16 and 16 labeled matching values V01 through V16. Each entity must use exactly one value from its allowed list, and every value must be used exactly once.

## Entities and allowed matching values
[P01] V01, V10, V07, V08
[P02] V15, V14, V05, V08
[P03] V01, V03, V10, V02
[P04] V16, V05, V07, V11
[P05] V13, V07, V12, V05
[P06] V01, V07, V16, V15
[P07] V09, V01, V05, V13
[P08] V14, V08, V09, V06
[P09] V11, V06, V10, V13
[P10] V04, V11, V09, V12
[P11] V02, V15, V04, V09
[P12] V15, V14, V06, V02
[P13] V12, V16, V04, V06
[P14] V10, V02, V03, V16
[P15] V12, V11, V03, V14
[P16] V04, V03, V08, V13

## Counting groups
[G1] P01, P02, P06, P07, P08, P09, P10, P12, P14, P16
[G2] P01, P02, P03, P04, P07, P08, P11, P15
[G3] P01, P04, P07, P10, P12, P13, P14, P15
[G4] P01, P02, P03, P04, P08, P13, P14
[G5] P01, P05, P09, P10, P11, P13
[G6] P01, P02, P03, P06, P09, P11, P12, P13, P15
[G7] P01, P07, P08, P11, P13, P16
[G8] P03, P04, P06, P07, P08, P09, P11, P14, P16
[SG01] P04, P05, P06, P09, P11, P13, P15, P16
[SG02] P01, P09, P10, P11, P13, P14
[H1] V01, V02, V03, V04, V06, V07, V08, V11, V16
[H2] V01, V05, V08, V09, V10, V11, V12, V13
[H3] V02, V05, V08, V09, V11, V14, V16
[H4] V01, V03, V07, V09, V11, V12, V14, V15, V16
[H5] V01, V06, V07, V11, V14, V15
[H6] V01, V03, V04, V06, V08, V09, V12, V13, V15
[H7] V01, V05, V09, V10, V13, V14
[H8] V01, V04, V06, V07, V08, V13, V15, V16
[SH01] V02, V10, V14, V16
[SH01C] V01, V03, V04, V05, V06, V07, V08, V09, V11, V12, V13, V15
[SH02] V01, V07, V08, V09, V12, V13, V14, V16
[SH02C] V02, V03, V04, V05, V06, V10, V11, V15

Let N(G,H) be the number of entities in entity group G whose assigned value belongs to value group H.

## Public clues
[C01] P01=V08 holds if and only if P14=V03 holds.
[C02] P14=V03 holds if and only if P12=V15 holds.
[C03] P12=V15 holds if and only if P07=V09 holds.
[C04] P07=V09 holds if and only if P02=V14 holds.
[C05] N(G7,H7)+N(G5,H5)+N(G6,H1) = N(G7,H2)+N(G5,H8)+N(G3,H3)-2.
[C06] N(G2,H8)+N(G5,H1) = N(G5,H4)+N(G4,H1)-1.
[C07] N(G2,H5)+N(G5,H4) = N(G2,H8)+N(G5,H5)+2.
[C08] N(G1,H3)+N(G7,H8)+N(G6,H2) = N(G8,H1)+N(G8,H4)+N(G1,H5)-3.
[C09] N(G5,H3)+N(G6,H1) = N(G3,H3)+N(G4,H1)-2.
[S01] N(SG01,SH01) = N(SG01,SH01C)-4.
[S02] N(SG02,SH02) = N(SG02,SH02C).

## Target proposition
Entity P15 uses matching value V11.

## Output
If the target proposition holds in at least one valid complete assignment, output only YES; otherwise output only NO. Do not provide a rationale or other text.
```

## WIT · zh

[Original prompt](prompts/bijective_matching/zh/p100.md) · SHA-256: `392e0952612158bd125616548010b5cd25914674fc6cbaee435463690e5c4e1e`

```text
# WITNESS

## 场景
共有16个实体P01到P16，以及16个有标签匹配值V01到V16。每个实体必须从自己的允许列表中选择恰好一个值；每个值也必须恰好使用一次。

## 实体及允许匹配值
[P01] V01, V10, V07, V08
[P02] V15, V14, V05, V08
[P03] V01, V03, V10, V02
[P04] V16, V05, V07, V11
[P05] V13, V07, V12, V05
[P06] V01, V07, V16, V15
[P07] V09, V01, V05, V13
[P08] V14, V08, V09, V06
[P09] V11, V06, V10, V13
[P10] V04, V11, V09, V12
[P11] V02, V15, V04, V09
[P12] V15, V14, V06, V02
[P13] V12, V16, V04, V06
[P14] V10, V02, V03, V16
[P15] V12, V11, V03, V14
[P16] V04, V03, V08, V13

## 计数组
[G1] P01, P02, P06, P07, P08, P09, P10, P12, P14, P16
[G2] P01, P02, P03, P04, P07, P08, P11, P15
[G3] P01, P04, P07, P10, P12, P13, P14, P15
[G4] P01, P02, P03, P04, P08, P13, P14
[G5] P01, P05, P09, P10, P11, P13
[G6] P01, P02, P03, P06, P09, P11, P12, P13, P15
[G7] P01, P07, P08, P11, P13, P16
[G8] P03, P04, P06, P07, P08, P09, P11, P14, P16
[SG01] P04, P05, P06, P09, P11, P13, P15, P16
[SG02] P01, P09, P10, P11, P13, P14
[H1] V01, V02, V03, V04, V06, V07, V08, V11, V16
[H2] V01, V05, V08, V09, V10, V11, V12, V13
[H3] V02, V05, V08, V09, V11, V14, V16
[H4] V01, V03, V07, V09, V11, V12, V14, V15, V16
[H5] V01, V06, V07, V11, V14, V15
[H6] V01, V03, V04, V06, V08, V09, V12, V13, V15
[H7] V01, V05, V09, V10, V13, V14
[H8] V01, V04, V06, V07, V08, V13, V15, V16
[SH01] V02, V10, V14, V16
[SH01C] V01, V03, V04, V05, V06, V07, V08, V09, V11, V12, V13, V15
[SH02] V01, V07, V08, V09, V12, V13, V14, V16
[SH02C] V02, V03, V04, V05, V06, V10, V11, V15

记 N(G,H) 为实体组 G 中最终取值属于值组 H 的实体数。

## 公开线索
[C01] P01=V08 与 P14=V03 要么同时成立，要么同时不成立。
[C02] P14=V03 与 P12=V15 要么同时成立，要么同时不成立。
[C03] P12=V15 与 P07=V09 要么同时成立，要么同时不成立。
[C04] P07=V09 与 P02=V14 要么同时成立，要么同时不成立。
[C05] N(G7,H7)+N(G5,H5)+N(G6,H1) = N(G7,H2)+N(G5,H8)+N(G3,H3)-2.
[C06] N(G2,H8)+N(G5,H1) = N(G5,H4)+N(G4,H1)-1.
[C07] N(G2,H5)+N(G5,H4) = N(G2,H8)+N(G5,H5)+2.
[C08] N(G1,H3)+N(G7,H8)+N(G6,H2) = N(G8,H1)+N(G8,H4)+N(G1,H5)-3.
[C09] N(G5,H3)+N(G6,H1) = N(G3,H3)+N(G4,H1)-2.
[S01] N(SG01,SH01) = N(SG01,SH01C)-4.
[S02] N(SG02,SH02) = N(SG02,SH02C).

## 目标命题
实体 P15 使用匹配值 V11。

## 输出要求
若存在使目标命题成立的合法完整赋值，只输出一个裸 JSON 对象：键必须恰好是全部 16 个实体编号，值为对应匹配值。若不存在，只输出 NONE。不要添加包装字段、理由或其他文字。
```

## WIT · en

[Original prompt](prompts/bijective_matching/en/p004.md) · SHA-256: `7a5b0708c44da8fe82066a011338b6366ee5a846dda6155b2b4187151de7510a`

```text
# WITNESS

## Scenario
There are 16 entities P01 through P16 and 16 labeled matching values V01 through V16. Each entity must use exactly one value from its allowed list, and every value must be used exactly once.

## Entities and allowed matching values
[P01] V01, V10, V07, V08
[P02] V15, V14, V05, V08
[P03] V01, V03, V10, V02
[P04] V16, V05, V07, V11
[P05] V13, V07, V12, V05
[P06] V01, V07, V16, V15
[P07] V09, V01, V05, V13
[P08] V14, V08, V09, V06
[P09] V11, V06, V10, V13
[P10] V04, V11, V09, V12
[P11] V02, V15, V04, V09
[P12] V15, V14, V06, V02
[P13] V12, V16, V04, V06
[P14] V10, V02, V03, V16
[P15] V12, V11, V03, V14
[P16] V04, V03, V08, V13

## Counting groups
[G1] P01, P02, P06, P07, P08, P09, P10, P12, P14, P16
[G2] P01, P02, P03, P04, P07, P08, P11, P15
[G3] P01, P04, P07, P10, P12, P13, P14, P15
[G4] P01, P02, P03, P04, P08, P13, P14
[G5] P01, P05, P09, P10, P11, P13
[G6] P01, P02, P03, P06, P09, P11, P12, P13, P15
[G7] P01, P07, P08, P11, P13, P16
[G8] P03, P04, P06, P07, P08, P09, P11, P14, P16
[SG01] P04, P05, P06, P09, P11, P13, P15, P16
[SG02] P01, P09, P10, P11, P13, P14
[H1] V01, V02, V03, V04, V06, V07, V08, V11, V16
[H2] V01, V05, V08, V09, V10, V11, V12, V13
[H3] V02, V05, V08, V09, V11, V14, V16
[H4] V01, V03, V07, V09, V11, V12, V14, V15, V16
[H5] V01, V06, V07, V11, V14, V15
[H6] V01, V03, V04, V06, V08, V09, V12, V13, V15
[H7] V01, V05, V09, V10, V13, V14
[H8] V01, V04, V06, V07, V08, V13, V15, V16
[SH01] V02, V10, V14, V16
[SH01C] V01, V03, V04, V05, V06, V07, V08, V09, V11, V12, V13, V15
[SH02] V01, V07, V08, V09, V12, V13, V14, V16
[SH02C] V02, V03, V04, V05, V06, V10, V11, V15

Let N(G,H) be the number of entities in entity group G whose assigned value belongs to value group H.

## Public clues
[C01] P01=V08 holds if and only if P14=V03 holds.
[C02] P14=V03 holds if and only if P12=V15 holds.
[C03] P12=V15 holds if and only if P07=V09 holds.
[C04] P07=V09 holds if and only if P02=V14 holds.
[C05] N(G7,H7)+N(G5,H5)+N(G6,H1) = N(G7,H2)+N(G5,H8)+N(G3,H3)-2.
[C06] N(G2,H8)+N(G5,H1) = N(G5,H4)+N(G4,H1)-1.
[C07] N(G2,H5)+N(G5,H4) = N(G2,H8)+N(G5,H5)+2.
[C08] N(G1,H3)+N(G7,H8)+N(G6,H2) = N(G8,H1)+N(G8,H4)+N(G1,H5)-3.
[C09] N(G5,H3)+N(G6,H1) = N(G3,H3)+N(G4,H1)-2.
[S01] N(SG01,SH01) = N(SG01,SH01C)-4.
[S02] N(SG02,SH02) = N(SG02,SH02C).

## Target proposition
Entity P15 uses matching value V11.

## Output
If a valid complete assignment satisfying the target proposition exists, output only one bare JSON object whose keys are exactly all 16 entity IDs and whose values are matching-value labels. If none exists, output exactly NONE. Do not add wrapper fields, a rationale, or other text.
```

## CEX · zh

[Original prompt](prompts/bijective_matching/zh/p097.md) · SHA-256: `0e2f76f08d63d1f31ed2b30fa0f71f3b569e1a7c2e4dbe4f44b792aa05a5582e`

```text
# COUNTEREXAMPLE

## 场景
共有16个实体P01到P16，以及16个有标签匹配值V01到V16。每个实体必须从自己的允许列表中选择恰好一个值；每个值也必须恰好使用一次。

## 实体及允许匹配值
[P01] V01, V10, V07, V08
[P02] V15, V14, V05, V08
[P03] V01, V03, V10, V02
[P04] V16, V05, V07, V11
[P05] V13, V07, V12, V05
[P06] V01, V07, V16, V15
[P07] V09, V01, V05, V13
[P08] V14, V08, V09, V06
[P09] V11, V06, V10, V13
[P10] V04, V11, V09, V12
[P11] V02, V15, V04, V09
[P12] V15, V14, V06, V02
[P13] V12, V16, V04, V06
[P14] V10, V02, V03, V16
[P15] V12, V11, V03, V14
[P16] V04, V03, V08, V13

## 计数组
[G1] P01, P02, P06, P07, P08, P09, P10, P12, P14, P16
[G2] P01, P02, P03, P04, P07, P08, P11, P15
[G3] P01, P04, P07, P10, P12, P13, P14, P15
[G4] P01, P02, P03, P04, P08, P13, P14
[G5] P01, P05, P09, P10, P11, P13
[G6] P01, P02, P03, P06, P09, P11, P12, P13, P15
[G7] P01, P07, P08, P11, P13, P16
[G8] P03, P04, P06, P07, P08, P09, P11, P14, P16
[SG01] P04, P05, P06, P09, P11, P13, P15, P16
[SG02] P01, P09, P10, P11, P13, P14
[H1] V01, V02, V03, V04, V06, V07, V08, V11, V16
[H2] V01, V05, V08, V09, V10, V11, V12, V13
[H3] V02, V05, V08, V09, V11, V14, V16
[H4] V01, V03, V07, V09, V11, V12, V14, V15, V16
[H5] V01, V06, V07, V11, V14, V15
[H6] V01, V03, V04, V06, V08, V09, V12, V13, V15
[H7] V01, V05, V09, V10, V13, V14
[H8] V01, V04, V06, V07, V08, V13, V15, V16
[SH01] V02, V10, V14, V16
[SH01C] V01, V03, V04, V05, V06, V07, V08, V09, V11, V12, V13, V15
[SH02] V01, V07, V08, V09, V12, V13, V14, V16
[SH02C] V02, V03, V04, V05, V06, V10, V11, V15

记 N(G,H) 为实体组 G 中最终取值属于值组 H 的实体数。

## 公开线索
[C01] P01=V08 与 P14=V03 要么同时成立，要么同时不成立。
[C02] P14=V03 与 P12=V15 要么同时成立，要么同时不成立。
[C03] P12=V15 与 P07=V09 要么同时成立，要么同时不成立。
[C04] P07=V09 与 P02=V14 要么同时成立，要么同时不成立。
[C05] N(G7,H7)+N(G5,H5)+N(G6,H1) = N(G7,H2)+N(G5,H8)+N(G3,H3)-2.
[C06] N(G2,H8)+N(G5,H1) = N(G5,H4)+N(G4,H1)-1.
[C07] N(G2,H5)+N(G5,H4) = N(G2,H8)+N(G5,H5)+2.
[C08] N(G1,H3)+N(G7,H8)+N(G6,H2) = N(G8,H1)+N(G8,H4)+N(G1,H5)-3.
[C09] N(G5,H3)+N(G6,H1) = N(G3,H3)+N(G4,H1)-2.
[S01] N(SG01,SH01) = N(SG01,SH01C)-4.
[S02] N(SG02,SH02) = N(SG02,SH02C).

## 目标命题
实体 P15 使用匹配值 V11。

## 输出要求
若存在使目标命题不成立的合法完整赋值，只输出一个裸 JSON 对象：键必须恰好是全部 16 个实体编号，值为对应匹配值。若不存在，只输出 NONE。不要添加包装字段、理由或其他文字。
```

## CEX · en

[Original prompt](prompts/bijective_matching/en/p001.md) · SHA-256: `8bfe8f5ea301005a01a1126477de3beb74ff4811129a582520a7f276b8d1b494`

```text
# COUNTEREXAMPLE

## Scenario
There are 16 entities P01 through P16 and 16 labeled matching values V01 through V16. Each entity must use exactly one value from its allowed list, and every value must be used exactly once.

## Entities and allowed matching values
[P01] V01, V10, V07, V08
[P02] V15, V14, V05, V08
[P03] V01, V03, V10, V02
[P04] V16, V05, V07, V11
[P05] V13, V07, V12, V05
[P06] V01, V07, V16, V15
[P07] V09, V01, V05, V13
[P08] V14, V08, V09, V06
[P09] V11, V06, V10, V13
[P10] V04, V11, V09, V12
[P11] V02, V15, V04, V09
[P12] V15, V14, V06, V02
[P13] V12, V16, V04, V06
[P14] V10, V02, V03, V16
[P15] V12, V11, V03, V14
[P16] V04, V03, V08, V13

## Counting groups
[G1] P01, P02, P06, P07, P08, P09, P10, P12, P14, P16
[G2] P01, P02, P03, P04, P07, P08, P11, P15
[G3] P01, P04, P07, P10, P12, P13, P14, P15
[G4] P01, P02, P03, P04, P08, P13, P14
[G5] P01, P05, P09, P10, P11, P13
[G6] P01, P02, P03, P06, P09, P11, P12, P13, P15
[G7] P01, P07, P08, P11, P13, P16
[G8] P03, P04, P06, P07, P08, P09, P11, P14, P16
[SG01] P04, P05, P06, P09, P11, P13, P15, P16
[SG02] P01, P09, P10, P11, P13, P14
[H1] V01, V02, V03, V04, V06, V07, V08, V11, V16
[H2] V01, V05, V08, V09, V10, V11, V12, V13
[H3] V02, V05, V08, V09, V11, V14, V16
[H4] V01, V03, V07, V09, V11, V12, V14, V15, V16
[H5] V01, V06, V07, V11, V14, V15
[H6] V01, V03, V04, V06, V08, V09, V12, V13, V15
[H7] V01, V05, V09, V10, V13, V14
[H8] V01, V04, V06, V07, V08, V13, V15, V16
[SH01] V02, V10, V14, V16
[SH01C] V01, V03, V04, V05, V06, V07, V08, V09, V11, V12, V13, V15
[SH02] V01, V07, V08, V09, V12, V13, V14, V16
[SH02C] V02, V03, V04, V05, V06, V10, V11, V15

Let N(G,H) be the number of entities in entity group G whose assigned value belongs to value group H.

## Public clues
[C01] P01=V08 holds if and only if P14=V03 holds.
[C02] P14=V03 holds if and only if P12=V15 holds.
[C03] P12=V15 holds if and only if P07=V09 holds.
[C04] P07=V09 holds if and only if P02=V14 holds.
[C05] N(G7,H7)+N(G5,H5)+N(G6,H1) = N(G7,H2)+N(G5,H8)+N(G3,H3)-2.
[C06] N(G2,H8)+N(G5,H1) = N(G5,H4)+N(G4,H1)-1.
[C07] N(G2,H5)+N(G5,H4) = N(G2,H8)+N(G5,H5)+2.
[C08] N(G1,H3)+N(G7,H8)+N(G6,H2) = N(G8,H1)+N(G8,H4)+N(G1,H5)-3.
[C09] N(G5,H3)+N(G6,H1) = N(G3,H3)+N(G4,H1)-2.
[S01] N(SG01,SH01) = N(SG01,SH01C)-4.
[S02] N(SG02,SH02) = N(SG02,SH02C).

## Target proposition
Entity P15 uses matching value V11.

## Output
If a valid complete assignment falsifying the target proposition exists, output only one bare JSON object whose keys are exactly all 16 entity IDs and whose values are matching-value labels. If none exists, output exactly NONE. Do not add wrapper fields, a rationale, or other text.
```
