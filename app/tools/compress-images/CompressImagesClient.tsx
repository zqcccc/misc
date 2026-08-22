'use client';

import JSZip from 'jszip';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';

type ExportType = 'same' | 'image/jpeg' | 'image/png' | 'image/webp';
type SizeMode = 'percent' | 'maxWidth';

interface ImgItem {
  id: string;
  file: File;
  preview: string;
  origSize: number;
  // 原始像素尺寸
  origW: number;
  origH: number;
  // 压缩结果
  status: 'pending' | 'processing' | 'done' | 'error';
  resultUrl?: string;
  resultSize?: number;
  resultType?: string;
  resultName?: string;
  errorMsg?: string;
}

const EXPORT_OPTIONS: { label: string; value: ExportType }[] = [
  { label: '同类型', value: 'same' },
  { label: 'JPG', value: 'image/jpeg' },
  { label: 'PNG', value: 'image/png' },
  { label: 'WEBP', value: 'image/webp' },
];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function compressRatio(orig: number, now: number): number {
  if (orig <= 0) return 0;
  return (1 - now / orig) * 100;
}

function ratioColor(ratio: number): string {
  // 压缩率越高（节省越多）越绿
  if (ratio >= 30) return 'text-green-600 dark:text-green-400';
  if (ratio >= 10) return 'text-blue-600 dark:text-blue-400';
  if (ratio >= 0) return 'text-gray-500 dark:text-gray-400';
  return 'text-red-500 dark:text-red-400'; // 变大了
}

function getFileId(file: File) {
  return `${file.name}_${file.size}_${file.lastModified}`;
}

// 根据导出类型决定最终的 mime
function resolveMime(exportType: ExportType, file: File): string {
  if (exportType === 'same') {
    const t = file.type;
    if (t === 'image/png' || t === 'image/jpeg' || t === 'image/webp') return t;
    // 其它类型（gif/bmp 等）fallback 到 jpeg
    return 'image/jpeg';
  }
  return exportType;
}

function extForMime(mime: string): string {
  if (mime === 'image/png') return 'png';
  if (mime === 'image/webp') return 'webp';
  return 'jpg';
}

function baseName(name: string): string {
  const idx = name.lastIndexOf('.');
  return idx > 0 ? name.slice(0, idx) : name;
}

async function compressOne(
  file: File,
  dataUrl: string,
  opts: { exportType: ExportType; sizeMode: SizeMode; percent: number; maxWidth: number; quality: number },
): Promise<{ blob: Blob; mime: string; name: string }> {
  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const im = new window.Image();
    im.onload = () => resolve(im);
    im.onerror = () => reject(new Error('图片解析失败'));
    im.src = dataUrl;
  });

  let newW = img.width;
  let newH = img.height;
  if (opts.sizeMode === 'percent' && opts.percent < 100) {
    newW = Math.max(1, Math.round((img.width * opts.percent) / 100));
    newH = Math.max(1, Math.round((img.height * opts.percent) / 100));
  } else if (opts.sizeMode === 'maxWidth' && opts.maxWidth > 0 && img.width > opts.maxWidth) {
    const ratio = opts.maxWidth / img.width;
    newW = opts.maxWidth;
    newH = Math.max(1, Math.round(img.height * ratio));
  }

  const canvas = document.createElement('canvas');
  canvas.width = newW;
  canvas.height = newH;
  const ctx = canvas.getContext('2d')!;

  const mime = resolveMime(opts.exportType, file);

  // JPEG/WebP 无透明通道，填白底避免透明区变黑
  if (mime === 'image/jpeg') {
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, newW, newH);
  }

  // 高质量缩放
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, 0, 0, newW, newH);

  const quality = mime === 'image/png' ? undefined : opts.quality / 100;

  const blob: Blob = await new Promise((resolve, reject) => {
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error('压缩失败'))),
      mime,
      quality,
    );
  });

  const name = `${baseName(file.name)}.${extForMime(mime)}`;
  return { blob, mime, name };
}

export default function CompressImagesClient() {
  const [items, setItems] = useState<ImgItem[]>([]);
  const [exportType, setExportType] = useState<ExportType>('same');
  const [sizeMode, setSizeMode] = useState<SizeMode>('percent');
  const [percent, setPercent] = useState(100);
  const [maxWidth, setMaxWidth] = useState(1920);
  const [quality, setQuality] = useState(80);
  const [dragOver, setDragOver] = useState(false);
  const [compressing, setCompressing] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);

  const opts = useMemo(
    () => ({ exportType, sizeMode, percent, maxWidth, quality }),
    [exportType, sizeMode, percent, maxWidth, quality],
  );

  // 添加文件
  const addFiles = useCallback(async (files: FileList | File[]) => {
    const arr = Array.from(files).filter((f) => f.type.startsWith('image/'));
    if (arr.length === 0) {
      toast.warning('请选择图片文件');
      return;
    }
    const newItems: ImgItem[] = [];
    for (const f of arr) {
      const id = getFileId(f);
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(f);
      });
      // 读取原始尺寸
      const dims = await new Promise<{ w: number; h: number }>((resolve) => {
        const im = new window.Image();
        im.onload = () => resolve({ w: im.width, h: im.height });
        im.onerror = () => resolve({ w: 0, h: 0 });
        im.src = dataUrl;
      });
      newItems.push({
        id,
        file: f,
        preview: dataUrl,
        origSize: f.size,
        origW: dims.w,
        origH: dims.h,
        status: 'pending',
      });
    }
    setItems((prev) => {
      const map = new Map(prev.map((it) => [it.id, it]));
      for (const ni of newItems) map.set(ni.id, ni);
      return Array.from(map.values());
    });
  }, []);

  // 压缩全部（设置变化或新增文件后自动触发）
  const runCompress = useCallback(
    async (list: ImgItem[], options: typeof opts) => {
      setCompressing(true);
      // 标记 processing
      setItems((prev) => prev.map((it) => ({ ...it, status: it.status === 'error' ? 'pending' : it.status === 'done' ? 'processing' : it.status })));
      const results = await Promise.all(
        list.map(async (it): Promise<{ id: string } & Partial<ImgItem>> => {
          try {
            const { blob, mime, name } = await compressOne(it.file, it.preview, options);
            const url = URL.createObjectURL(blob);
            return {
              id: it.id,
              status: 'done' as const,
              resultUrl: url,
              resultSize: blob.size,
              resultType: mime,
              resultName: name,
              errorMsg: undefined,
            };
          } catch (e: any) {
            return {
              id: it.id,
              status: 'error' as const,
              errorMsg: e?.message || '压缩失败',
              resultUrl: undefined,
              resultSize: undefined,
            };
          }
        }),
      );
      const byId = new Map(results.map((r) => [r.id, r]));
      setItems((prev) =>
        prev.map((it) => {
          const r = byId.get(it.id);
          if (!r) return it;
          // 释放旧的 objectURL 避免内存泄漏
          if (r.resultUrl && it.resultUrl) {
            URL.revokeObjectURL(it.resultUrl);
          }
          const { id: _id, ...rest } = r;
          return { ...it, ...rest };
        }),
      );
      setCompressing(false);
    },
    [],
  );

  // 设置变化或文件增减 → 重新压缩（debounce）
  useEffect(() => {
    if (items.length === 0) return;
    const t = setTimeout(() => {
      runCompress(items, opts);
    }, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts, items.map((i) => i.id).join(',')]);

  // 粘贴上传
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      if (!e.clipboardData) return;
      const files: File[] = [];
      for (const it of Array.from(e.clipboardData.items)) {
        if (it.kind === 'file') {
          const f = it.getAsFile();
          if (f) files.push(f);
        }
      }
      if (files.length > 0) addFiles(files);
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [addFiles]);

  // 卸载时释放 objectURL
  useEffect(() => {
    return () => {
      items.forEach((it) => {
        if (it.resultUrl) URL.revokeObjectURL(it.resultUrl);
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(e.target.files);
    e.target.value = '';
  };

  // 拖拽
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer.types?.includes('Files')) setDragOver(true);
  };
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setDragOver(false);
    }
  };
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setDragOver(false);
    if (e.dataTransfer.files) addFiles(e.dataTransfer.files);
  };

  const removeItem = (id: string) => {
    setItems((prev) => {
      const target = prev.find((it) => it.id === id);
      if (target?.resultUrl) URL.revokeObjectURL(target.resultUrl);
      return prev.filter((it) => it.id !== id);
    });
  };

  const clearAll = () => {
    items.forEach((it) => {
      if (it.resultUrl) URL.revokeObjectURL(it.resultUrl);
    });
    setItems([]);
  };

  const downloadOne = (it: ImgItem) => {
    if (!it.resultUrl || !it.resultName) return;
    const a = document.createElement('a');
    a.href = it.resultUrl;
    a.download = it.resultName;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const downloadAll = async () => {
    const done = items.filter((it) => it.status === 'done' && it.resultUrl);
    if (done.length === 0) {
      toast.warning('没有可下载的图片');
      return;
    }
    if (done.length === 1) {
      downloadOne(done[0]);
      return;
    }
    try {
      const zip = new JSZip();
      // 解决重名
      const used = new Map<string, number>();
      for (const it of done) {
        let name = it.resultName || `${baseName(it.file.name)}.bin`;
        if (used.has(name)) {
          const n = used.get(name)! + 1;
          used.set(name, n);
          const dot = name.lastIndexOf('.');
          name = dot > 0 ? `${name.slice(0, dot)}(${n})${name.slice(dot)}` : `${name}(${n})`;
        } else {
          used.set(name, 0);
        }
        // fetch blob from objectURL
        const resp = await fetch(it.resultUrl!);
        const blob = await resp.blob();
        zip.file(name, blob);
      }
      const zipBlob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(zipBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `compressed-${Date.now()}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(`已打包 ${done.length} 张图片`);
    } catch (e: any) {
      toast.error('打包下载失败: ' + (e?.message || ''));
    }
  };

  const stats = useMemo(() => {
    const done = items.filter((it) => it.status === 'done' && it.resultSize != null);
    const totalOrig = done.reduce((s, it) => s + it.origSize, 0);
    const totalNew = done.reduce((s, it) => s + (it.resultSize || 0), 0);
    const totalRatio = compressRatio(totalOrig, totalNew);
    return { count: done.length, totalOrig, totalNew, totalRatio };
  }, [items]);

  const qualityEnabled = exportType !== 'image/png';

  return (
    <div>
      {/* 拖拽上传区 */}
      <div
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative cursor-pointer rounded-2xl border-2 border-dashed transition-all duration-200 ${
          dragOver
            ? 'border-blue-500 bg-blue-50/80 dark:bg-blue-900/20 scale-[1.01]'
            : 'border-gray-300 dark:border-gray-600 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-gray-50 dark:hover:bg-[#363c48]'
        } ${items.length === 0 ? 'p-14' : 'p-6'}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFileChange}
          className="hidden"
        />
        <div className="flex flex-col items-center text-center pointer-events-none">
          <div className={`mb-3 flex items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 text-white shadow-lg ${items.length === 0 ? 'w-16 h-16' : 'w-12 h-12'} transition-all`}>
            <svg className={items.length === 0 ? 'w-8 h-8' : 'w-6 h-6'} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.9A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
            </svg>
          </div>
          {items.length === 0 ? (
            <>
              <p className="text-lg font-semibold text-gray-800 dark:text-gray-100">
                点击、拖拽或粘贴上传图片
              </p>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                支持 JPG / PNG / WEBP，可多选，浏览器本地处理
              </p>
            </>
          ) : (
            <p className="text-sm font-medium text-blue-600 dark:text-blue-400">
              + 继续添加图片（拖拽 / 粘贴 / 点击）
            </p>
          )}
        </div>
      </div>

      {/* 设置面板 */}
      {items.length > 0 && (
        <div className="mt-6 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-[#363c48] p-5">
          <div className="grid gap-5 sm:grid-cols-2">
            {/* 导出类型 */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
                导出图片类型
              </label>
              <div className="flex flex-wrap gap-2">
                {EXPORT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setExportType(opt.value)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                      exportType === opt.value
                        ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                        : 'bg-white dark:bg-[#282c35] text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-600 hover:border-blue-400 dark:hover:border-blue-500'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 尺寸限制 */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
                尺寸限制
              </label>
              <div className="flex items-center gap-3">
                <div className="flex rounded-lg overflow-hidden border border-gray-300 dark:border-gray-600">
                  <button
                    onClick={() => setSizeMode('percent')}
                    className={`px-3 py-1.5 text-sm ${sizeMode === 'percent' ? 'bg-blue-600 text-white' : 'bg-white dark:bg-[#282c35] text-gray-700 dark:text-gray-200'}`}
                  >
                    百分比
                  </button>
                  <button
                    onClick={() => setSizeMode('maxWidth')}
                    className={`px-3 py-1.5 text-sm border-l border-gray-300 dark:border-gray-600 ${sizeMode === 'maxWidth' ? 'bg-blue-600 text-white' : 'bg-white dark:bg-[#282c35] text-gray-700 dark:text-gray-200'}`}
                  >
                    最大宽度
                  </button>
                </div>
                {sizeMode === 'percent' ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={percent}
                      onChange={(e) => setPercent(Math.max(1, Math.min(100, Number(e.target.value) || 100)))}
                      className="w-20 px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-[#282c35] text-gray-900 dark:text-gray-100 text-sm"
                    />
                    <span className="text-gray-500 dark:text-gray-400 text-sm">%</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={1}
                      value={maxWidth}
                      onChange={(e) => setMaxWidth(Math.max(1, Number(e.target.value) || 1920))}
                      className="w-24 px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-[#282c35] text-gray-900 dark:text-gray-100 text-sm"
                    />
                    <span className="text-gray-500 dark:text-gray-400 text-sm">px</span>
                  </div>
                )}
              </div>
            </div>

            {/* 图像质量 */}
            {qualityEnabled && (
              <div className="sm:col-span-2">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                    图像质量
                  </label>
                  <span className="text-sm font-bold text-blue-600 dark:text-blue-400">{quality}%</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={100}
                  value={quality}
                  onChange={(e) => setQuality(Number(e.target.value))}
                  className="w-full accent-blue-600"
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* 统计 + 操作 */}
      {items.length > 0 && (
        <div className="mt-6 flex flex-wrap items-center gap-4 justify-between">
          <div className="flex flex-wrap items-center gap-5 text-sm">
            <span className="text-gray-600 dark:text-gray-300">
              共 <b className="text-gray-900 dark:text-gray-100">{items.length}</b> 张
              {stats.count > 0 && (
                <>
                  <span className="mx-2 text-gray-300 dark:text-gray-600">|</span>
                  原始 <b className="text-gray-900 dark:text-gray-100">{formatBytes(stats.totalOrig)}</b>
                  <span className="mx-1 text-gray-400">→</span>
                  压缩后 <b className="text-gray-900 dark:text-gray-100">{formatBytes(stats.totalNew)}</b>
                  <span className={`ml-2 font-bold ${ratioColor(stats.totalRatio)}`}>
                    {stats.totalRatio >= 0 ? `节省 ${stats.totalRatio.toFixed(1)}%` : `增大 ${(-stats.totalRatio).toFixed(1)}%`}
                  </span>
                </>
              )}
            </span>
            {compressing && (
              <span className="inline-flex items-center gap-1.5 text-blue-600 dark:text-blue-400">
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
                  <path d="M12 2a10 10 0 0110 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                </svg>
                压缩中…
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={clearAll}
              className="px-4 py-2 rounded-lg text-sm font-medium border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#444b5a] transition-colors"
            >
              清空
            </button>
            <button
              onClick={downloadAll}
              disabled={stats.count === 0}
              className={`px-5 py-2 rounded-lg text-sm font-semibold shadow transition-colors ${
                stats.count === 0
                  ? 'bg-gray-200 dark:bg-[#363c48] text-gray-400 dark:text-gray-500 cursor-not-allowed'
                  : 'bg-green-600 hover:bg-green-700 text-white'
              }`}
            >
              {stats.count > 1 ? `下载全部 (${stats.count}) ZIP` : '下载图片'}
            </button>
          </div>
        </div>
      )}

      {/* 文件列表 */}
      {items.length > 0 && (
        <div className="mt-5 space-y-3">
          {items.map((it) => {
            const ratio = it.resultSize != null ? compressRatio(it.origSize, it.resultSize) : null;
            return (
              <div
                key={it.id}
                className="flex items-center gap-4 p-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] shadow-sm"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={it.status === 'done' && it.resultUrl ? it.resultUrl : it.preview}
                  alt={it.file.name}
                  className="w-16 h-16 object-cover rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-[#363c48] flex-shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">
                    {it.file.name}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-500 dark:text-gray-400">
                    {it.origW > 0 && <span>{it.origW}×{it.origH}</span>}
                    <span>{formatBytes(it.origSize)}</span>
                    {it.status === 'done' && it.resultSize != null && (
                      <>
                        <span className="text-gray-400">→</span>
                        <span className="text-gray-700 dark:text-gray-200 font-medium">{formatBytes(it.resultSize)}</span>
                        {ratio != null && (
                          <span className={`font-bold ${ratioColor(ratio)}`}>
                            {ratio >= 0 ? `-${ratio.toFixed(1)}%` : `+${(-ratio).toFixed(1)}%`}
                          </span>
                        )}
                      </>
                    )}
                    {it.status === 'error' && (
                      <span className="text-red-500">{it.errorMsg}</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {it.status === 'done' && (
                    <button
                      onClick={() => downloadOne(it)}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium border border-green-300 dark:border-green-700 text-green-700 dark:text-green-400 bg-green-50 dark:bg-[#2a3a2a] hover:bg-green-100 dark:hover:bg-[#3a4a3a] transition-colors"
                    >
                      下载
                    </button>
                  )}
                  <button
                    onClick={() => removeItem(it.id)}
                    className="px-2.5 py-1.5 rounded-lg text-xs font-medium border border-red-200 dark:border-red-700 text-red-600 dark:text-red-400 bg-red-50 dark:bg-[#4b2323] hover:bg-red-100 dark:hover:bg-[#6b2c2c] transition-colors"
                    aria-label="删除"
                  >
                    ✕
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
