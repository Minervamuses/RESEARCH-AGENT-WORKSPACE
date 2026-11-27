---
title: Multi-level Research Paper Fixture
author: Test Author
# YAML comment must not appear in outline
---

# 1. Introduction

This is an introductory paragraph. Try typing `[@` below inside a project with `references.json` to test Markdown citation completion, press Esc, then type a key prefix or press Ctrl+Space.

Ordinary academic prose here should never trigger word-based suggestions.

## 1.1 Research Motivation

Some background text with **bold** and *italic* phrasing.

> # Quoted heading must be excluded from outline

- # Unordered list heading must be excluded
  ## Indented heading inside list must be excluded

### 1.1.1 Specific **Questions** and [`Tools`](https://example.com)

```markdown
# Heading inside fenced code block must be excluded
```

<!--
# Heading inside HTML comment must be excluded
-->

# 2. Methodology

Details of the methodology.

## 2.1 Data Collection

Description of data sources and preprocessing.

### 2.1.1 Inclusion Criteria

Paragraph 1.

Paragraph 2.

Paragraph 3.

#### 2.1.1.1 Edge Case Handling

Deep level-4 heading for nesting and indentation verification.

## 2.2 Experimental Setup

More content to ensure vertical scrolling space above the conclusion.

Line A.

Line B.

Line C.

Line D.

Line E.

Line F.

Setext Level-1 Heading
======================

Setext Level-2 Heading
----------------------

# 3. Results and Discussion

Summary of empirical findings across benchmarks.

## 3.1 Quantitative Analysis

Numbers and ablations.

## 3.2 Error Analysis

Qualitative failure modes.

# 4. Conclusion

This final section intentionally has only two lines so clicking Conclusion tests bottom-of-file active-section stability.
Final closing sentence.
