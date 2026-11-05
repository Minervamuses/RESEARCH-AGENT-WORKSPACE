---
title: "Synthetic @notacite corpus"
---

# Heading with @h1key

Plain [@a; @b] and [see @c, p. 33; also @d, ch. 2] and [-@e].
In-text @f says, and @g [p. 3] adds. Braced @{h.i}x and @{weird key}.
Trailing punctuation @key:sub. and @end. Then @q?. Then @a_b-c:d#e.
Email jane@doe.com and 見@wang2020 but 見 @wang2021 研究（@wang2022）。
Example (@ex1) vs (@ex.2) and \@escaped and `@code` and ``@dbl `x` @y``.
<!-- @comment
spanning @lines -->
Math $x @m$ and $$@mm$$ but price $5 @cash.
Autolink <https://x.com/@user> but bare https://x.com/@bare and <a@b.org>.
Emoji 😀 then @emoji1 and 𝒳 @emoji2.
Link [@inlink](http://x) and [@ref][r] and [text @inbr more].
**@bold** _@ital_ *@star* word,@comma (@a) (@zz-1).

```python
@decorator
def f(): pass
```

~~~
@tilde
~~~

    @indented code

- list item @li1
    continued @li2

> quote @quote

| table | @tab |
|---|---|
| @cell | x |

[^1]: Footnote @fn.

Final@notcite @last
