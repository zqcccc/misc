'use client';

import Image from 'next/image';
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from '@dnd-kit/utilities';

const LAYOUTS = [
  { label: "纵向", value: "vertical" },
  { label: "横向", value: "horizontal" },
];
function getSizeModes(layout: string) {
  return [
    { label: layout === 'vertical' ? '等宽' : '等高', value: 'equal-width' },
    { label: '原始大小', value: 'original' },
  ];
}
const BASE_MODES = [
  { label: '最大', value: 'max' },
  { label: '最小', value: 'min' },
  { label: '自定义', value: 'custom' },
];
function getFileId(file: File) {
  return `${file.name}_${file.size}_${file.lastModified}`;
}
function SortableImage({ id, src, name, onMoveUp, onMoveDown, onRemove, index, total }: any) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    position: 'relative' as 'relative',
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="flex items-center gap-4 mb-4 p-3 bg-gray-50 dark:bg-[#363c48] border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm cursor-grab relative"
    >
      <Image
        src={src}
        alt={name}
        unoptimized
        width={80}
        height={80}
        className="w-20 h-20 object-cover rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35]"
      />
      <div className="flex-1">
        <div className="text-sm text-gray-800 dark:text-gray-200 mb-1 truncate">{name}</div>
        <div className="flex gap-2">
          <button
            onClick={onMoveUp}
            disabled={index === 0}
            className={`px-2 py-0.5 rounded border text-xs ${index === 0 ? 'bg-gray-100 dark:bg-[#282c35] border-gray-200 dark:border-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed' : 'bg-gray-100 dark:bg-[#363c48] border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-[#444b5a]'}`}
          >
            ↑ 上移
          </button>
          <button
            onClick={onMoveDown}
            disabled={index === total - 1}
            className={`px-2 py-0.5 rounded border text-xs ${index === total - 1 ? 'bg-gray-100 dark:bg-[#282c35] border-gray-200 dark:border-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed' : 'bg-gray-100 dark:bg-[#363c48] border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-[#444b5a]'}`}
          >
            ↓ 下移
          </button>
          <button
            onClick={onRemove}
            className="px-2 py-0.5 rounded border border-red-200 dark:border-red-700 bg-red-50 dark:bg-[#4b2323] text-red-600 dark:text-red-400 text-xs hover:bg-red-100 dark:hover:bg-[#6b2c2c]"
          >
            删除
          </button>
        </div>
      </div>
      <span className="absolute right-3 top-3 text-xs text-gray-400 dark:text-gray-500 select-none">拖拽排序</span>
    </div>
  );
}

export default function MergeImagesClient() {
  const [fileObjs, setFileObjs] = useState<{ id: string; file: File; preview: string }[]>([]);
  const [layout, setLayout] = useState("vertical");
  const [sizeMode, setSizeMode] = useState("equal-width");
  const [baseMode, setBaseMode] = useState<'max' | 'min' | 'custom'>('max');
  const [customBase, setCustomBase] = useState('');
  const [imgStats, setImgStats] = useState<{ minWidth: number; maxWidth: number; minHeight: number; maxHeight: number } | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [resultSize, setResultSize] = useState<{ width: number; height: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [quality, setQuality] = useState(90);
  const [outputType, setOutputType] = useState<'image/png' | 'image/jpeg' | 'image/webp'>('image/png');

  // 下载文件名跟随导出格式；两个下载入口共用同一文件名
  const resultFileName = `merged.${outputType === 'image/jpeg' ? 'jpg' : outputType === 'image/webp' ? 'webp' : 'png'}`;

  const sensors = useSensors(useSensor(PointerSensor));

  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);
  const loadSeq = useRef(0);

  // 旧合成结果整体作废：data URL 直接清出状态，交给 GC
  const invalidateResult = useCallback(() => {
    setResultUrl(null);
    setResultSize(null);
  }, []);

  // 设置版本号：合并进行期间任一设置变更都会递增，完成的结果据此作废
  const settingsVersionRef = useRef(0);

  // 设置变更统一入口：值确实变化时先落新值，再立即作废旧结果（布局/尺寸基准/质量/格式均不得复用旧产物）
  const changeSetting = useCallback((changed: boolean, apply: () => void) => {
    if (!changed) return;
    apply();
    settingsVersionRef.current++;
    invalidateResult();
  }, [invalidateResult]);

  const loadFiles = useCallback((files: File[]) => {
    if (files.length === 0) return;
    const seq = ++loadSeq.current;
    Promise.all(files.map(f => {
      const { promise, resolve, reject } = Promise.withResolvers<{ id: string; file: File; preview: string }>();
      const reader = new FileReader();
      reader.onload = () => resolve({ id: getFileId(f), file: f, preview: reader.result as string });
      reader.onerror = reject;
      reader.readAsDataURL(f);
      return promise;
    })).then(async (objs) => {
      if (seq !== loadSeq.current) return;
      setFileObjs(objs);
      invalidateResult();
      const imgs = await Promise.all(
        objs.map(obj => {
          const { promise, resolve, reject } = Promise.withResolvers<HTMLImageElement>();
          const img = new window.Image();
          img.onload = () => resolve(img);
          img.onerror = reject;
          img.src = obj.preview;
          return promise;
        })
      );
      if (seq !== loadSeq.current) return;
      const widths = imgs.map(img => img.width);
      const heights = imgs.map(img => img.height);
      setImgStats({
        minWidth: Math.min(...widths),
        maxWidth: Math.max(...widths),
        minHeight: Math.min(...heights),
        maxHeight: Math.max(...heights),
      });
    });
  }, [invalidateResult]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) loadFiles(Array.from(e.target.files));
    e.target.value = '';
  };

  // 粘贴上传
  useEffect(() => {
    const onPaste = (ev: ClipboardEvent) => {
      if (!ev.clipboardData) return;
      const files: File[] = [];
      for (const it of Array.from(ev.clipboardData.items)) {
        if (it.kind === 'file') {
          const f = it.getAsFile();
          if (f) files.push(f);
        }
      }
      if (files.length > 0) loadFiles(files);
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [loadFiles]);

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
    if (e.dataTransfer.files) loadFiles(Array.from(e.dataTransfer.files));
  };

  const moveUp = (idx: number) => {
    if (idx === 0) return;
    const arr = fileObjs.slice();
    [arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]];
    setFileObjs(arr);
    invalidateResult();
  };
  const moveDown = (idx: number) => {
    if (idx === fileObjs.length - 1) return;
    const arr = fileObjs.slice();
    [arr[idx + 1], arr[idx]] = [arr[idx], arr[idx + 1]];
    setFileObjs(arr);
    invalidateResult();
  };
  const remove = (idx: number) => {
    const arr = fileObjs.slice();
    arr.splice(idx, 1);
    setFileObjs(arr);
    invalidateResult();
  };

  const handleDragEnd = (event: any) => {
    const { active, over } = event;
    if (active.id !== over?.id) {
      const oldIndex = fileObjs.findIndex((f) => f.id === active.id);
      const newIndex = fileObjs.findIndex((f) => f.id === over.id);
      setFileObjs((arr) => arrayMove(arr, oldIndex, newIndex));
      invalidateResult();
    }
  };

  const handleMerge = async () => {
    if (fileObjs.length === 0) return;
    setLoading(true);
    const startVersion = settingsVersionRef.current;
    try {
      // 复用上传时已读出的 data URL 解码，不再对同一批文件做第二次 FileReader
      const images = await Promise.all(
        fileObjs.map((obj) => {
          const { promise, resolve, reject } = Promise.withResolvers<HTMLImageElement>();
          const img = new window.Image();
          img.onload = () => resolve(img);
          img.onerror = reject;
          img.src = obj.preview;
          return promise;
        })
      );
      let canvasWidth = 0;
      let canvasHeight = 0;
      let baseValue = 0;
      if (layout === "vertical") {
        if (sizeMode === "equal-width") {
          const widths = images.map(img => img.width);
          if (baseMode === 'max') baseValue = Math.max(...widths);
          else if (baseMode === 'min') baseValue = Math.min(...widths);
          else baseValue = Number(customBase) || Math.max(...widths);
          canvasWidth = baseValue;
          canvasHeight = images.reduce(
            (sum, img) => sum + Math.round((img.height * baseValue) / img.width),
            0
          );
        } else {
          canvasWidth = Math.max(...images.map((img) => img.width));
          canvasHeight = images.reduce((sum, img) => sum + img.height, 0);
        }
      } else {
        if (sizeMode === "equal-width") {
          const heights = images.map(img => img.height);
          if (baseMode === 'max') baseValue = Math.max(...heights);
          else if (baseMode === 'min') baseValue = Math.min(...heights);
          else baseValue = Number(customBase) || Math.max(...heights);
          canvasHeight = baseValue;
          canvasWidth = images.reduce(
            (sum, img) => sum + Math.round((img.width * baseValue) / img.height),
            0
          );
        } else {
          canvasHeight = Math.max(...images.map((img) => img.height));
          canvasWidth = images.reduce((sum, img) => sum + img.width, 0);
        }
      }
      const canvas = document.createElement("canvas");
      canvas.width = canvasWidth;
      canvas.height = canvasHeight;
      const ctx = canvas.getContext("2d")!;
      let offsetX = 0;
      let offsetY = 0;
      for (const img of images) {
        let drawWidth = img.width;
        let drawHeight = img.height;
        if (layout === "vertical" && sizeMode === "equal-width") {
          drawWidth = canvasWidth;
          drawHeight = Math.round((img.height * canvasWidth) / img.width);
        } else if (layout === "horizontal" && sizeMode === "equal-width") {
          drawHeight = canvasHeight;
          drawWidth = Math.round((img.width * canvasHeight) / img.height);
        }
        ctx.drawImage(img, offsetX, offsetY, drawWidth, drawHeight);
        if (layout === "vertical") {
          offsetY += drawHeight;
        } else {
          offsetX += drawWidth;
        }
      }
      let dataUrl: string;
      if (outputType === 'image/png') {
        dataUrl = canvas.toDataURL('image/png');
      } else {
        dataUrl = canvas.toDataURL(outputType, quality / 100);
      }
      // 合并期间设置被改动：本轮结果作废，不写入
      if (settingsVersionRef.current !== startVersion) return;
      setResultUrl(dataUrl);
      setResultSize({ width: canvasWidth, height: canvasHeight });
    } catch (err) {
      alert("图片合并失败: " + (err as any)?.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto my-10 p-8 bg-white dark:bg-[#282c35] rounded-xl shadow-lg transition-colors">
      <div
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative mb-6 rounded-2xl border-2 border-dashed transition-all duration-200 ${
          dragOver
            ? 'border-blue-500 bg-blue-50/80 dark:bg-blue-900/20 scale-[1.01]'
            : 'border-gray-300 dark:border-gray-600 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-gray-50 dark:hover:bg-[#363c48]'
        }`}
      >
        <label
          className={`block cursor-pointer rounded-2xl focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500 focus-within:bg-blue-50/80 dark:focus-within:bg-blue-900/20 ${
            fileObjs.length === 0 ? 'p-12' : 'p-6'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={handleFileChange}
            className="sr-only"
          />
          <div className="flex items-center gap-4 pointer-events-none">
          <div className={`flex-shrink-0 flex items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 text-white shadow-lg ${fileObjs.length === 0 ? 'w-14 h-14' : 'w-12 h-12'} transition-all`}>
            <svg className={fileObjs.length === 0 ? 'w-7 h-7' : 'w-6 h-6'} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.9A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
            </svg>
          </div>
          <div>
            {fileObjs.length === 0 ? (
              <>
                <p className="text-base font-semibold text-gray-800 dark:text-gray-100">
                  点击、拖拽或粘贴上传图片
                </p>
                <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
                  支持多图，上传后可拖拽排序或用按钮调整顺序
                </p>
              </>
            ) : (
              <p className="text-sm font-medium text-blue-600 dark:text-blue-400">
                已选 {fileObjs.length} 张 · 点击/拖拽/粘贴可重新选择
              </p>
            )}
          </div>
        </div>
        </label>
      </div>
      {fileObjs.length > 0 && (
        <div className="mb-8 bg-gray-50 dark:bg-[#363c48] rounded-lg p-5 shadow">
          <div className="font-semibold mb-3 text-gray-700 dark:text-gray-100">图片顺序预览</div>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={fileObjs.map(f => f.id)} strategy={verticalListSortingStrategy}>
              {fileObjs.map((f, idx) => (
                <SortableImage
                  key={f.id}
                  id={f.id}
                  src={f.preview}
                  name={f.file.name}
                  index={idx}
                  total={fileObjs.length}
                  onMoveUp={() => moveUp(idx)}
                  onMoveDown={() => moveDown(idx)}
                  onRemove={() => remove(idx)}
                />
              ))}
            </SortableContext>
          </DndContext>
        </div>
      )}
      <div className="mb-6 flex flex-wrap gap-8 items-center">
        <div>
          <span className="font-medium">排列方式：</span>
          {LAYOUTS.map((item) => (
            <label key={item.value} className="mr-4 text-base">
              <input
                type="radio"
                name="layout"
                value={item.value}
                checked={layout === item.value}
                onChange={() => changeSetting(layout !== item.value, () => setLayout(item.value))}
                className="mr-1"
              />
              {item.label}
            </label>
          ))}
        </div>
        <div>
          <span className="font-medium">尺寸模式：</span>
          {getSizeModes(layout).map((item) => (
            <label key={item.value} className="mr-4 text-base">
              <input
                type="radio"
                name="sizeMode"
                value={item.value}
                checked={sizeMode === item.value}
                onChange={() => changeSetting(sizeMode !== item.value, () => setSizeMode(item.value))}
                className="mr-1"
              />
              {item.label}
            </label>
          ))}
        </div>
        {sizeMode === 'equal-width' && (
          <div className="ml-4">
            <span className="font-medium">基准{layout === 'vertical' ? '宽度' : '高度'}：</span>
            {BASE_MODES.map((item) => (
              <label key={item.value} className="mr-2 text-base">
                <input
                  type="radio"
                  name="baseMode"
                  value={item.value}
                  checked={baseMode === item.value}
                  onChange={() => changeSetting(baseMode !== item.value, () => setBaseMode(item.value as any))}
                  className="mr-1"
                />
                {item.label}
              </label>
            ))}
            {baseMode === 'custom' && (
              <input
                type="number"
                min={1}
                value={customBase}
                onChange={e => changeSetting(customBase !== e.target.value, () => setCustomBase(e.target.value))}
                placeholder={layout === 'vertical' ? '宽度(px)' : '高度(px)'}
                className="w-20 ml-1 px-2 py-0.5 rounded border border-gray-300 dark:border-gray-600 text-sm bg-white dark:bg-[#282c35] text-gray-900 dark:text-gray-100"
              />
            )}
            {imgStats && (
              <span className="text-gray-400 text-xs ml-2">
                (最小: {layout === 'vertical' ? imgStats.minWidth : imgStats.minHeight}px, 最大: {layout === 'vertical' ? imgStats.maxWidth : imgStats.maxHeight}px)
              </span>
            )}
          </div>
        )}
      </div>
      <div className="mb-6 flex items-center gap-4">
        <label className="font-medium mr-2">导出格式：</label>
        <select
          value={outputType}
          onChange={e => changeSetting(outputType !== e.target.value, () => setOutputType(e.target.value as any))}
          className="border rounded px-2 py-1 bg-white dark:bg-[#282c35] text-gray-900 dark:text-gray-100 border-gray-300 dark:border-gray-600"
        >
          <option value="image/png">PNG（无损）</option>
          <option value="image/jpeg">JPEG（有损，可调质量）</option>
          <option value="image/webp">WebP（可调质量）</option>
        </select>
      </div>
      {outputType !== 'image/png' && (
        <div className="mb-6 flex items-center gap-4">
          <label className="font-medium mr-2">输出图片质量：</label>
          <input
            type="range"
            min={1}
            max={100}
            value={quality}
            onChange={e => changeSetting(quality !== Number(e.target.value), () => setQuality(Number(e.target.value)))}
            className="w-48 accent-blue-600"
          />
          <span className="ml-2 text-blue-700 dark:text-blue-300 font-semibold w-10 inline-block">{quality}%</span>
        </div>
      )}
      <div className="flex items-center gap-4 mb-2">
        <button
          onClick={handleMerge}
          disabled={fileObjs.length === 0 || loading}
          className={`px-9 py-2 text-lg rounded-md font-semibold shadow transition-colors ${fileObjs.length === 0 || loading ? 'bg-gray-200 dark:bg-[#363c48] text-gray-400 dark:text-gray-500 cursor-not-allowed' : 'bg-blue-600 dark:bg-blue-800 text-white hover:bg-blue-700 dark:hover:bg-blue-900'}`}
        >
          {loading ? "合并中..." : "合并图片"}
        </button>
        {resultUrl && (
          <a
            href={resultUrl}
            download={resultFileName}
            className="px-6 py-2 text-lg rounded-md font-semibold shadow bg-green-600 dark:bg-green-800 text-white hover:bg-green-700 dark:hover:bg-green-900 transition-colors"
          >
            下载图片
          </a>
        )}
      </div>
      {resultUrl && (
        <div className="mt-10 text-center bg-gray-50 dark:bg-[#363c48] rounded-lg p-6 shadow">
          <h3 className="font-semibold mb-4 text-gray-900 dark:text-gray-100">合成结果</h3>
          <Image
            src={resultUrl}
            alt="合成图片"
            unoptimized
            width={resultSize?.width ?? 1}
            height={resultSize?.height ?? 1}
            className="max-w-full border border-gray-200 dark:border-gray-700 mb-4 rounded bg-white dark:bg-[#282c35] inline-block"
            style={{ maxWidth: '100%', height: 'auto' }}
          />
          <div>
            <a href={resultUrl} download={resultFileName} className="text-blue-600 dark:text-blue-300 font-medium text-base hover:underline">
              下载图片
            </a>
          </div>
        </div>
      )}
    </div>
  );
} 
