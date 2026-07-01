"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

const CANVAS_WIDTH = 500;
const CANVAS_HEIGHT = 200;
const DEFAULT_THRESHOLD = 200;

type Point = { x: number; y: number };

function canvasToPngFile(canvas: HTMLCanvasElement, filename: string): Promise<File> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("Failed to export canvas as PNG"));
        return;
      }
      resolve(new File([blob], filename, { type: "image/png" }));
    }, "image/png");
  });
}

/** Fades light (background-ish) pixels to transparent; keeps darker ink pixels opaque. */
function fadeLightPixelsToTransparent(imageData: ImageData, threshold: number) {
  const data = imageData.data;
  for (let i = 0; i < data.length; i += 4) {
    const luminance = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    if (luminance > threshold) {
      const fade = ((luminance - threshold) / (255 - threshold)) * 255;
      data[i + 3] = Math.min(data[i + 3], Math.round(255 - fade));
    }
  }
}

function pointFromEvent(canvas: HTMLCanvasElement, e: PointerEvent<HTMLCanvasElement>): Point {
  const rect = canvas.getBoundingClientRect();
  return {
    x: ((e.clientX - rect.left) / rect.width) * canvas.width,
    y: ((e.clientY - rect.top) / rect.height) * canvas.height,
  };
}

export type SignaturePadProps = {
  onSave?: (file: File) => void | Promise<void>;
  className?: string;
};

export function SignaturePad({ onSave, className }: SignaturePadProps) {
  const drawCanvasRef = useRef<HTMLCanvasElement>(null);
  const uploadCanvasRef = useRef<HTMLCanvasElement>(null);
  const isDrawingRef = useRef(false);
  const lastPointRef = useRef<Point | null>(null);

  const [hasStrokes, setHasStrokes] = useState(false);
  const [uploadedImage, setUploadedImage] = useState<HTMLImageElement>();
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [saving, setSaving] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function handlePointerDown(e: PointerEvent<HTMLCanvasElement>) {
    const canvas = drawCanvasRef.current;
    if (!canvas) return;
    e.preventDefault();
    canvas.setPointerCapture(e.pointerId);
    isDrawingRef.current = true;
    lastPointRef.current = pointFromEvent(canvas, e);
  }

  function handlePointerMove(e: PointerEvent<HTMLCanvasElement>) {
    const canvas = drawCanvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || !isDrawingRef.current || !lastPointRef.current) return;
    const point = pointFromEvent(canvas, e);
    ctx.strokeStyle = "#1e293b";
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(lastPointRef.current.x, lastPointRef.current.y);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
    lastPointRef.current = point;
    setHasStrokes(true);
  }

  function handlePointerUp(e: PointerEvent<HTMLCanvasElement>) {
    isDrawingRef.current = false;
    lastPointRef.current = null;
    drawCanvasRef.current?.releasePointerCapture(e.pointerId);
  }

  function clearDrawing() {
    const canvas = drawCanvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasStrokes(false);
  }

  async function saveDrawnSignature() {
    const canvas = drawCanvasRef.current;
    if (!canvas || !hasStrokes) return;
    setError(undefined);
    setSaving(true);
    try {
      const file = await canvasToPngFile(canvas, `signature-${Date.now()}.png`);
      setPreviewUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return URL.createObjectURL(file);
      });
      await onSave?.(file);
    } catch (err) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  }

  function handleFileSelect(file: File) {
    setError(undefined);
    const img = new Image();
    img.onload = () => setUploadedImage(img);
    img.onerror = () => setError("Could not read that image file");
    img.src = URL.createObjectURL(file);
  }

  // Re-render the background-removed preview whenever the source image or threshold changes.
  useEffect(() => {
    if (!uploadedImage) return;
    const canvas = uploadCanvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    canvas.width = uploadedImage.naturalWidth;
    canvas.height = uploadedImage.naturalHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(uploadedImage, 0, 0);
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    fadeLightPixelsToTransparent(imageData, threshold);
    ctx.putImageData(imageData, 0, 0);
  }, [uploadedImage, threshold]);

  async function saveUploadedSignature() {
    const canvas = uploadCanvasRef.current;
    if (!canvas || !uploadedImage) return;
    setError(undefined);
    setSaving(true);
    try {
      const file = await canvasToPngFile(canvas, `signature-${Date.now()}.png`);
      setPreviewUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return URL.createObjectURL(file);
      });
      await onSave?.(file);
    } catch (err) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <Tabs defaultValue="draw">
        <TabsList>
          <TabsTrigger value="draw">Draw</TabsTrigger>
          <TabsTrigger value="upload">Upload image</TabsTrigger>
        </TabsList>

        <TabsContent value="draw" className="flex flex-col gap-3">
          <canvas
            ref={drawCanvasRef}
            width={CANVAS_WIDTH}
            height={CANVAS_HEIGHT}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerLeave={handlePointerUp}
            className="checkered-bg w-full touch-none rounded-lg border"
            style={{ aspectRatio: `${CANVAS_WIDTH} / ${CANVAS_HEIGHT}` }}
          />
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={clearDrawing} disabled={!hasStrokes}>
              Clear
            </Button>
            <Button type="button" onClick={() => void saveDrawnSignature()} disabled={!hasStrokes || saving}>
              {saving ? "Saving..." : "Save signature"}
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="upload" className="flex flex-col gap-3">
          <Input
            type="file"
            accept="image/png,image/jpeg"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFileSelect(file);
            }}
          />
          {uploadedImage && (
            <>
              <div className="flex flex-col gap-2">
                <Label>Background removal sensitivity</Label>
                <Slider
                  min={100}
                  max={250}
                  step={5}
                  value={[threshold]}
                  onValueChange={(value) => setThreshold(Array.isArray(value) ? value[0] : value)}
                />
              </div>
              <canvas ref={uploadCanvasRef} className="checkered-bg max-h-48 w-full rounded-lg border object-contain" />
              <Button type="button" onClick={() => void saveUploadedSignature()} disabled={saving}>
                {saving ? "Saving..." : "Save signature"}
              </Button>
            </>
          )}
        </TabsContent>
      </Tabs>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {previewUrl && (
        <div className="flex flex-col gap-2">
          <Label>Saved signature preview</Label>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={previewUrl} alt="Saved signature" className="checkered-bg h-24 w-auto rounded-lg border" />
        </div>
      )}
    </div>
  );
}
