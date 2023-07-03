---
title: 国际化实践2
date: "2023-02-28"
description: "再次代码国际化实践"
---

代码：https://github.com/zqcccc/temp/tree/6f116f8d85f7fbdf91d77d36fcc6d413f96560b0/parser

调试地址：https://astexplorer.net/

万万没想到，公司还有项目要做国际化，还不止一个，原来做过一次国际化替换代码，本来是要复用脚本去做的，但是发现有很多问题，之前的脚本替换的时候把一些没有用的字符也匹配进去了，而且所有的模板字符串都没有匹配到，于是决定来重写一下脚本。

整体流程倒是没有变，主要是遍历 `ast` 的过程的修改，分析了一下，会匹配到中文的就三种类型的节点 `StringLiteral`、`JSXText`、`TemplateLiteral`

|                   | 解释                   | 示例                                                     |
| ----------------- | ---------------------- | -------------------------------------------------------- |
| `StringLiteral`   | `JS` 普通字符串        | `var a = '你好, world'` 中的 `'你好, world'`             |
| `JSXText`         | `JSX` 标签中的正常文本 | `<div>你好</div>` 中的 `你好`                            |
| `TemplateLiteral` | 模板字符串             | `` var a = `你好, ${name}` `` 中的 `` `你好, ${name}` `` |

在这三种类型节点中把中文提出来后，会把中文替换成调用一个函数 `t`，参数是一个 id，这个函数 `t` 会根据不同的语言设置返回不同的语言的字符串，例如上面的 `var a = '你好, world'` 我们会改成 ``var a = `${t('id1')}, world` `` 这个 `id1` 是随便取的名字，只要定义好这个 id 到各个语言的映射就行了

很巧的是，这三种类型最后都会变成 `TemplateLiteral`，`JSXText` 还要加上一对花括号以在 `jsx` 中变成 `expressions` 使用，那组装成 `TemplateLiteral` 类型的节点就成了关键

一个 `TemplateLiteral` 由两个数组构成，`quasis` 和 `expressions` 数组，`quasis` 数组里其实就是普通的字符串，它的长度一定比 `expressions` 数组多一个（是我试错才试出来的），这样的设计就是为了把两个数组拼接成模板字符串的时候，一定不会有顺序上的歧义，这样看 `babel` 真的很巧妙

https://github.com/zqcccc/temp/blob/6f116f8d85/parser/changeCode.cjs

替换过程中的一些边界 case 也让我不停地修改了脚本，代码写的有点冗余，但是结果还是挺满意的，核心就是这个组装新 `TemplateLiteral` 节点的函数 `getTemplateLiteralArguments` 了

```js
function getTemplateLiteralArguments(
  map,
  quasis,
  expressions,
  callback,
  flags = {}
) {
  const newQuasis = []
  const newExpressions = []
  const all = [...quasis, ...expressions]
  all.sort((a, b) => a.start - b.start)

  all.forEach((node) => {
    if (node.type !== 'TemplateElement') {
      newExpressions.push(node)
      return
    }
    let value = node.value.raw
    const allCNs = value.match(/(?<cn>[\u4e00-\u9fa5]+)/g)
    allCNs &&
      allCNs.forEach((cn) => {
        callback?.(cn)
        if (!map[cn]) {
          console.log('*****not found: ', cn)
          return
        }
        const cnLeft = value.indexOf(cn)
        const beforeText = value.slice(0, cnLeft)
        const afterText = value.slice(cnLeft + cn.length)
        value = afterText
        newQuasis.push(types.TemplateElement({ raw: beforeText }))
        newExpressions.push(
          types.CallExpression(
            types.Identifier(flags.useI18n ? 'i18n.t' : 't'),
            [
              hackStringValue(map[cn]),
              flags.tWithMoreArgs &&
                types.objectExpression([
                  types.objectProperty(
                    types.identifier('lng'),
                    types.identifier('i18n.language')
                  ),
                ]),
            ].filter(Boolean)
          )
        )
      })
    newQuasis.push(types.TemplateElement({ raw: value }))
  })
  //     console.log('middle quasis', newQuasis)
  //     console.log('middle expressions', newExpressions)
  return [newQuasis, newExpressions]
}
```

`StringLiteral` 和 `JSXText` 的情况就是把字符串丢到 `quasis` 数组里，`expressions` 数组是空的

我们这个 `getTemplateLiteralArguments` 函数其实一上来就是把 `quasis` 数组和 `expressions` 数组合并了，并重新排序（babel 在合并的时候也是按照顺序去合并的，我们也要按照顺序去遍历）

最开始我是用正则去匹配的，但是就是不好用，因为如果一个字符串里只有中文，那结果就类似于 `` `${t('id')}` `` ，这样的情况下字符串数组里就是两个空字符串，用正则的迭代器去匹配的时候，什么时候去插入空字符串我不太确定（有大佬知道可以告知一下），于是我就把所有的匹配到的中文段都先拿到，然后再去不停的切割，保证正确才是我们的第一优先级，毕竟我们这是在用脚本改人写的代码

执行 `getTemplateLiteralArguments` 拿到这两个数组后就替换节点，不停的循环走完一个文件，拿到转换后的代码字符串后用 prettier 美化一下，然后覆盖写入文件，然后不停的循环这个过程

关于在替换代码的过程中去引入 `t` 函数的部分还不是很好（我是假设我们的代码都是用的 `hooks` 写法），其实替换后的代码一跑起来，`eslint` 就会提示你哪里的 `hooks` 用的有问题了，有问题就删除那行引用，也比较简单，所以还不算很麻烦，就懒得去研究这部分的逻辑了
