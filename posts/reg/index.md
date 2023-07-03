---
title: 正则
date: '2020-11-01T22:12:03.284Z'
description: 'Hello World, first post~'
slug: 'learn-webpack'
---

有一道题是这样的，将给定的数字转化成千分位的格式，如把“10000”转化为“10,000”

```javascript{22}
// js逻辑写法
function transform(num) {
  num = (num + '').split('')

  var temp = []
  var count = 0

  for (var len = num.length, i = len - 1; i >= 0; i--) {
    temp.unshift(num[i])
    count += 1
    if (count % 3 === 0 && i != 0) {
      temp.unshift(',')
    }
  }
  return temp.join('')
}

// 正则写法
function transform(num) {
  num = num + ''

  return num.replace(/(?=(?!\b)(\d{3})+$)/g, ',')
}
```

正则

```JavaScript
var reg = /(?=(?!\b)(\d{3})+$)/g // 对象字面量声明 /pattern/flag
var reg = new RegExp('(?=(?!\\b)(\\d{3})+$)', 'g') // 构造函数声明正则，其实就是去掉了两边的 / 而且里面的每个 \ 都要转义
```

正则是跨语言的存在，很多语言的正则都是参考了 Perl 的正则实现

正则最重要的是它的思维

正则表达的是对字符串的一种过滤逻辑，主要是匹配（位置）和获取（字符）

pattern 是有规则的字符集，也是正则的主要内容

## 基本语法

| [xyz] | 一个字符集，匹配任意一个包含的字符 | [^xyz] | 一个否定字符集，匹配任何未包含的字符 |
| ----- | ---------------------------------- | ------ | ------------------------------------ |
| \w    | 匹配字母或数字或下划线的字符       | \W     | 匹配不是字母，数字，下划线的字符     |
| \d    | 匹配数字                           | \D     | 匹配非数字的字符                     |
| \s    | 匹配**任意**空白符                 | \S     | 匹配不是空白符的字符                 |
| \b    | 匹配单词的开始或结束的位置         | \B     | 匹配不是单词开头或结束的位置         |
| ^     | 匹配字符串的开始                   | $      | 匹配字符串的结束                     |

## 通配符和正则表达式的区别

通配符用于匹配文件名，完全匹配

| 通配符 | 作 用                                                                                      |
| ------ | ------------------------------------------------------------------------------------------ |
| `?`    | 匹配一个任意字符                                                                           |
| `*`    | 匹配 0 个或任意多个任意字符，也就是可以匹配任何内容                                        |
| `[]`   | 匹配中括号中任意一个字符。例如，`[abc]` 代表一定匹配一个字符，或者是 a，或者是 b，或者是 c |
| `[-]`  | 匹配中括号中任意一个字符，-代表一个范围。例如，`[a-z]` 代表匹配一个小写字母                |
| `[^]`  | 逻辑非，表示匹配不是中括号内的一个字符。例如，`[^0-9]` 代表匹配一个不是数字的字符          |

## RegExp 对象

console.dir() 可以打印 RegExp 对象

方法

- test() 返回 true 或者 false
- exec() 返回一个类数组，其实是个对象，返回的结果中的 "0" 项是完全匹配的字符串，一般没什么用，但 "1" 项会返回捕获分组的结果就很有用

属性

- source 返回当前正则表达式对象的模式文本的字符串不包含 // 和 标志位
- ignoreCase 标志位 i 忽略大小写
- global 标志位 g 全局匹配 用 string.match() 可以拿出所有匹配的字符串
- multiline 标志位 m 有换行符 \n 可以匹配多行

## 重复（量词）

| \*       | 重复 0 次或更多次，相当于 \{0, \} |
| -------- | --------------------------------- |
| +        | 重复 1 次或更多次，相当于 \{1, \} |
| ？       | 重复 0 次或 1 次，相当于 \{0,1\}  |
| \{n\}    | 重复 n 次，相当于 \{n,n\}         |
| \{n, \}  | 重复 n 次或更多次                 |
| \{n, m\} | 重复 n 次到 m 次                  |

匹配邮箱的正则可能是 `/^[0-9a-z\-.]+@[0-9a-z\-.]+$/`

```javascript
var reg = /^https?:\/\/q{2}\.com\/$/
console.log(reg.test('https://qq.com/'))
```

## 分组与捕获

() 里放要分组的正则，分组默认捕获，分组捕获也是我们最常用的概念

- 捕获型分组

  - 引用

  - 反向引用

- 非捕获型分组 在 () 里的开头 `?:`，使用非捕获型分组的原因是要用分组中可以使用“或者”的判断

捕获一个经典的例子就是去写一个通用的判断数据类型

```javascript
Object.prototype.toString
  .call(/*需要判断类型的数据放这*/ obj)
  .replace(/\[object (\S+)\]/, '$1')
  .toLowerCase()
```

### 引用和反向引用

```js
// 引用
var ret = /(jero) love (coding|girl)/.exec('jero love girl')
console.log(ret[1], RegExp.$1) // jero jero
// 直接从 RegExp.$1 可以拿到最近匹配的第一个分组结果，数字根据分组个数可以改变，没有 $0

// 反向引用
var reg1 = /<div>.*<\/div>/ // 这里的 div 出现了两次，可以改成下面的方式
var reg2 = /<(div)>.*<\/\1>/
console.log(reg2.test('<div>abcd</div>')) // true
// 括号嵌套问题
// \10 是\10 还是\1和0
// 引用不存在问题 直接转义数字
```

## 贪婪匹配和惰性匹配

- 贪婪（greedy）匹配：普通量词
- 惰性（lazy）匹配：普通量词加 `?`
  - 非贪婪，non-greedy

```javascript
// 贪婪匹配
/<(script)>.*<\/\1>/g.exec('<script>abcd</><script>efgh</script>') // 匹配整段

// 惰性匹配
/<(script)>.*?<\/script>/g.exec('<script>abcd</><script>efgh</script>') // 匹配第一小段
```

```js
var rSpan = /<span>.*?<\/span>/g
var s =
  '<strong>coding..$sf</span> is <span>interes^[+-ting</span><strong>codi_#ng</span> is <span>interesting</span><strong>co@ding</span>@ is@ <span>interesti$$ng</span><strong>c--oding</span> is <span>interesting</span>&&&<strong>coding</span> is <span>interesting</span>'

var ret = s.match(rSpan)
var length = ret && ret.length // 根据这个来判断对错的
console.log(length)
```

## 正向前瞻和负向前瞻

look ahead positive assert 正向前瞻（零宽断言）即后面有的匹配 `/jero(?= love coding)/`

look ahead negative assert 负向前瞻（负向零宽断言）即后面没有的匹配 `/jero(?! love coding)/`

它们是匹配位置的，虽然有小括号，但是并不会分组捕获

```js
var reg1 = /jero(?=\slove\scoding)/g
var reg2 = /jero(?!\slove\sgirl)/g
var target = 'jero love coding jero love girl jero love coding'

console.log(target.match(reg2)) // ["jero","jero"]

var target2 = 'img.jpg style.css script.js hello.jpg'
var reg3 = /\b(\w+)\.jpg\b/g // 这个也可以匹配但是，它会带上 .jpg 这个后缀，我们不需要这个后缀的时候就需要用到下面的这个正则写法
var reg3 = /\b(\w+)(?=\.jpg)\b/g // 去掉两个 \b 也可以
console.log(target2.match(reg3))
```

还有正向后瞻和负向后瞻，这个在 JS 中应该少用，因为[有兼容性问题](https://caniuse.com/?search=lookbehind%20assertions)

`(?<=foo)` 匹配前面是 `foo` 的

`(?<!foo)` 匹配前面不是 `foo` 的

```js
var s =
  '<div id="babalala">paragraph </div><p>哈哈哈</p><span class="yellow">hello jsonp!</span><strong>呵呵呵pi!</strong>'
var r = /<(\/?)(?!p|\/p).*?>/g

console.log(s.replace(r, '<$1p $2>'))
```

在 ES5 中，共有 6 个匹配位置的：

| 字符开始 | 字符结束 | 单词边界 | 非单词边界 | 后面得有 p | 后面不能有 p |
| -------- | -------- | -------- | ---------- | ---------- | ------------ |
| ^        | $        | \b       | \B         | (?=p)      | (?!p)        |

正则的规则主要是匹配位置和捕获字符

记住正则的这些规则后更重要的是去理解每一个正则表达式里面的思想

## String 对象

String 常用的能使用正则的方法

- replace()
- match()
  - 和正则对象的 exec() 相比，加了 g 标志的情况下，exec() 仍然只能匹配一个，而 match() 可以匹配全部

match 返回结果的格式，与正则对象是否有修饰符 g 有关。

```js
var string = '2017.06.27'
var regex1 = /\b(\d+)\b/
var regex2 = /\b(\d+)\b/g
console.log(string.match(regex1))
console.log(string.match(regex2))
// => ["2017", "2017", index: 0, input: "2017.06.27"]
// => ["2017", "06", "27"]
```

没有`g`，返回的是标准匹配格式，即，数组的第一个元素是整体匹配的内容，接下来是分组捕获的内容，然后是整体匹配的第一个下标，最后是输入的目标字符串。

有`g`，返回的是所有匹配的内容。

当没有匹配时，不管有无`g`，都返回`null`。

- split()
- search()
  - 返回 index，从 0 开始

## 方法比较

### **exec 比 match 更强大**

当正则没有`g`时，使用 `match` 返回的信息比较多。但是有`g`后，就没有关键的信息`index`了。

而`exec`方法就能解决这个问题，它能接着上一次匹配后继续匹配：

```js
var string = '2017.06.27'
var regex2 = /\b(\d+)\b/g
console.log(regex2.exec(string))
console.log(regex2.lastIndex)
console.log(regex2.exec(string))
console.log(regex2.lastIndex)
console.log(regex2.exec(string))
console.log(regex2.lastIndex)
console.log(regex2.exec(string))
console.log(regex2.lastIndex)
// => ["2017", "2017", index: 0, input: "2017.06.27"]
// => 4
// => ["06", "06", index: 5, input: "2017.06.27"]
// => 7
// => ["27", "27", index: 8, input: "2017.06.27"]
// => 10
// => null
// => 0
```

其中正则实例`lastIndex`属性，表示下一次匹配开始的位置。

比如第一次匹配了“2017”，开始下标是 0，共 4 个字符，因此这次匹配结束的位置是 3，下一次开始匹配的位置是 4。

从上述代码看出，在使用`exec`时，经常需要配合使用`while`循环：

```js
var string = '2017.06.27'
var regex2 = /\b(\d+)\b/g
var result
while ((result = regex2.exec(string))) {
  console.log(result, regex2.lastIndex)
}
// => ["2017", "2017", index: 0, input: "2017.06.27"] 4
// => ["06", "06", index: 5, input: "2017.06.27"] 7
// => ["27", "27", index: 8, input: "2017.06.27"] 10
```

### **修饰符 g，对 exex 和 test 的影响**

上面提到了正则实例的`lastIndex`属性，表示尝试匹配时，从字符串的`lastIndex`位开始去匹配。

字符串的四个方法，每次匹配时，都是从 0 开始的，即`lastIndex`属性始终不变。

而正则实例的两个方法`exec`、`test`，当正则是全局匹配时，每一次匹配完成后，都会修改`lastIndex`。下面让我们以`test`为例，看看你是否会迷糊：

```js
var regex = /a/g
console.log(regex.test('a'), regex.lastIndex)
console.log(regex.test('aba'), regex.lastIndex)
console.log(regex.test('ababc'), regex.lastIndex)
// => true 1
// => true 3
// => false 0
```

注意上面代码中的第三次调用`test`，因为这一次尝试匹配，开始从下标`lastIndex`即 3 位置处开始查找，自然就找不到了。

如果没有`g`，自然都是从字符串第 0 个字符处开始尝试匹配：

```js
var regex = /a/
console.log(regex.test('a'), regex.lastIndex)
console.log(regex.test('aba'), regex.lastIndex)
console.log(regex.test('ababc'), regex.lastIndex)
// => true 0
// => true 0
// => true 0
```

**split 相关注意事项**

`split`方法看起来不起眼，但要注意的地方有两个的。

第一，它可以有第二个参数，表示结果数组的最大长度：

```js
var string = 'html,css,javascript'
console.log(string.split(/,/, 2))
// =>["html", "css"]
复制代码
```

第二，正则使用分组时，结果数组中是包含分隔符的：

```js
var string = 'html,css,javascript'
console.log(string.split(/(,)/))
// =>["html", ",", "css", ",", "javascript"]
// 这里其实只要不捕获分组或者不分组就可以不包含分隔符
```

## 资源

[在线分析正则](https://regex101.com/)

[正则完整教程](https://juejin.cn/post/6844903487155732494)
