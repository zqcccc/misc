'use client';

import React, { useState } from "react";
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
      <img
        src={src}
        alt={name}
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
  const [loading, setLoading] = useState(false);
  const [quality, setQuality] = useState(90);
  const [outputType, setOutputType] = useState<'image/png' | 'image/jpeg' | 'image/webp'>('image/png');

  const sensors = useSensors(useSensor(PointerSensor));

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const arr = Array.from(e.target.files);
      Promise.all(arr.map(f => new Promise<{ id: string; file: File; preview: string }>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve({ id: getFileId(f), file: f, preview: reader.result as string });
        reader.onerror = reject;
        reader.readAsDataURL(f);
      }))).then(async (objs) => {
        setFileObjs(objs);
        setResultUrl(null);
        const imgs = await Promise.all(
          objs.map(obj => new Promise<HTMLImageElement>((resolve, reject) => {
            const img = new window.Image();
            img.onload = () => resolve(img);
            img.onerror = reject;
            img.src = obj.preview;
          }))
        );
        const widths = imgs.map(img => img.width);
        const heights = imgs.map(img => img.height);
        setImgStats({
          minWidth: Math.min(...widths),
          maxWidth: Math.max(...widths),
          minHeight: Math.min(...heights),
          maxHeight: Math.max(...heights),
        });
      });
    }
  };

  const moveUp = (idx: number) => {
    if (idx === 0) return;
    const arr = fileObjs.slice();
    [arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]];
    setFileObjs(arr);
  };
  const moveDown = (idx: number) => {
    if (idx === fileObjs.length - 1) return;
    const arr = fileObjs.slice();
    [arr[idx + 1], arr[idx]] = [arr[idx], arr[idx + 1]];
    setFileObjs(arr);
  };
  const remove = (idx: number) => {
    const arr = fileObjs.slice();
    arr.splice(idx, 1);
    setFileObjs(arr);
    setResultUrl(null);
  };

  const handleDragEnd = (event: any) => {
    const { active, over } = event;
    if (active.id !== over?.id) {
      const oldIndex = fileObjs.findIndex((f) => f.id === active.id);
      const newIndex = fileObjs.findIndex((f) => f.id === over.id);
      setFileObjs((arr) => arrayMove(arr, oldIndex, newIndex));
    }
  };

  // 合并图片
  const handleMerge = async () => {
    if (fileObjs.length === 0) return;
    setLoading(true);
    try {
      const images = await Promise.all(
        fileObjs.map(
          ({ file }) =>
            new Promise<HTMLImageElement>((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => {
                const img = new window.Image();
                img.onload = () => resolve(img);
                img.onerror = reject;
                img.src = reader.result as string;
              };
              reader.onerror = reject;
              reader.readAsDataURL(file);
            })
        )
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
      setResultUrl(dataUrl);
    } catch (err) {
      alert("图片合并失败: " + (err as any)?.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto my-10 p-8 bg-white dark:bg-[#282c35] rounded-xl shadow-lg transition-colors">
      <div className="mb-6 flex items-center gap-4">
        <label
          htmlFor="file-upload"
          className="inline-flex items-center px-4 py-2 bg-blue-600 dark:bg-blue-800 text-white rounded-md shadow cursor-pointer hover:bg-blue-700 dark:hover:bg-blue-900 transition-colors font-medium"
        >
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5-5m0 0l5 5m-5-5v12" />
          </svg>
          选择图片
          <input
            id="file-upload"
            type="file"
            accept="image/*"
            multiple
            onChange={handleFileChange}
            className="hidden"
          />
        </label>
        <span className="text-gray-400 dark:text-gray-500 text-sm">支持多图，拖拽/按钮调整顺序</span>
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
                onChange={() => setLayout(item.value)}
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
                onChange={() => setSizeMode(item.value)}
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
                  onChange={() => setBaseMode(item.value as any)}
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
                onChange={e => setCustomBase(e.target.value)}
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
          onChange={e => setOutputType(e.target.value as any)}
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
            onChange={e => setQuality(Number(e.target.value))}
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
            download="merged.png"
            className="px-6 py-2 text-lg rounded-md font-semibold shadow bg-green-600 dark:bg-green-800 text-white hover:bg-green-700 dark:hover:bg-green-900 transition-colors"
          >
            下载图片
          </a>
        )}
      </div>
      {resultUrl && (
        <div className="mt-10 text-center bg-gray-50 dark:bg-[#363c48] rounded-lg p-6 shadow">
          <h3 className="font-semibold mb-4 text-gray-900 dark:text-gray-100">合成结果</h3>
          <img src={resultUrl} alt="合成图片" className="max-w-full border border-gray-200 dark:border-gray-700 mb-4 rounded bg-white dark:bg-[#282c35] inline-block" />
          <div>
            <a href={resultUrl} download="merged.png" className="text-blue-600 dark:text-blue-300 font-medium text-base hover:underline">
              下载图片
            </a>
          </div>
        </div>
      )}
    </div>
  );
} 