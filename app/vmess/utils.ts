export const getClipboardText = async () => {
  try {
    const text = await navigator.clipboard.readText()
    return text
  } catch (error) {
    console.error('Failed to read clipboard contents: ', error)
    return ''
  }
}

export function getRandom<T = any>(arr: T[], m: number) {
  // 复制数组副本
  const nArray = arr.concat();
  const n = arr.length

  if (n <= m) {
    // 如果n小于等于m，直接返回原始数组的副本
    return nArray;
  }

  const resultArray = [];

  for (let i = 0; i < m; i++) {
    // 随机选择一个索引
    const randomIndex = Math.floor(Math.random() * nArray.length);

    // 将选中的元素添加到结果数组中
    resultArray.push(nArray[randomIndex]);

    // 从数组副本中移除已选中的元素
    nArray.splice(randomIndex, 1);
  }

  return resultArray;
}
