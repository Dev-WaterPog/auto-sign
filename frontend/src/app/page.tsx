"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SignaturePad } from "@/components/signature-pad";
import { ApiError, signDocumentByAnchor, signDocumentDirect, type SignaturePosition } from "@/lib/api";
import { clearAccessToken, getAccessToken, setAccessToken } from "@/lib/access-token";

type SignMode = "placeholder" | "anchor";

export default function Home() {
  const [templateFile, setTemplateFile] = useState<File>();
  const [signatureFile, setSignatureFile] = useState<File>();
  const [mode, setMode] = useState<SignMode>("placeholder");
  const [anchorText, setAnchorText] = useState("");
  const [position, setPosition] = useState<SignaturePosition>("right");
  const [dateValue, setDateValue] = useState("");
  const [signing, setSigning] = useState(false);
  const [error, setError] = useState<string>();
  const [placementWarning, setPlacementWarning] = useState<{ signaturePlaced: boolean; datePlaced: boolean }>();
  const [signedPdf, setSignedPdf] = useState<{ url: string; filename: string }>();

  const [accessToken, setAccessTokenState] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [authError, setAuthError] = useState<string>();

  // Revoke the previous blob URL whenever it's replaced or the page unmounts.
  useEffect(() => {
    return () => {
      if (signedPdf) URL.revokeObjectURL(signedPdf.url);
    };
  }, [signedPdf]);

  // Default the date picker to today, client-side only so SSR/hydration match.
  useEffect(() => {
    setDateValue(new Date().toISOString().slice(0, 10));
  }, []);

  // Read any previously-saved access code, client-side only.
  useEffect(() => {
    setAccessTokenState(getAccessToken());
  }, []);

  function handleGateSubmit() {
    if (!tokenInput.trim()) return;
    setAccessToken(tokenInput.trim());
    setAccessTokenState(tokenInput.trim());
    setAuthError(undefined);
  }

  async function handleSign() {
    if (!templateFile || !signatureFile) return;
    if (mode === "anchor" && !anchorText.trim()) {
      setError("Enter text to search for on the template (e.g. a name).");
      return;
    }
    setSigning(true);
    setError(undefined);
    setPlacementWarning(undefined);
    try {
      let blob: Blob;
      let filename: string;
      if (mode === "placeholder") {
        ({ blob, filename } = await signDocumentDirect(templateFile, signatureFile, dateValue || undefined));
      } else {
        const result = await signDocumentByAnchor({
          templateFile,
          signatureFile,
          signatureAnchor: anchorText,
          signaturePosition: position,
          dateValue: dateValue || undefined,
        });
        blob = result.blob;
        filename = result.filename;
        if (!result.signaturePlaced || !result.datePlaced) {
          setPlacementWarning({ signaturePlaced: result.signaturePlaced, datePlaced: result.datePlaced });
        }
      }
      setSignedPdf((prev) => {
        if (prev) URL.revokeObjectURL(prev.url);
        return { url: URL.createObjectURL(blob), filename };
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearAccessToken();
        setAccessTokenState("");
        setAuthError("Access code invalid or expired — enter it again.");
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSigning(false);
    }
  }

  if (!accessToken) {
    return (
      <div className="flex flex-1 items-center justify-center bg-zinc-50 px-4 dark:bg-black">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>Enter access code</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <Input
              type="password"
              placeholder="Access code"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleGateSubmit();
              }}
            />
            {authError && <p className="text-sm text-destructive">{authError}</p>}
            <Button onClick={handleGateSubmit} disabled={!tokenInput.trim()}>
              Continue
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-1 justify-center bg-zinc-50 px-4 py-16 dark:bg-black">
      <div className="flex w-full max-w-2xl flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Auto Sign</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-6">
            <div className="flex flex-col gap-2">
              <Label htmlFor="template-upload">1. Document template (PDF)</Label>
              <Input
                id="template-upload"
                type="file"
                accept="application/pdf"
                onChange={(e) => setTemplateFile(e.target.files?.[0])}
              />
              {templateFile && <p className="text-muted-foreground text-sm">Selected: {templateFile.name}</p>}
            </div>

            <div className="flex flex-col gap-2">
              <Label>2. Signature</Label>
              <SignaturePad onSave={(file) => setSignatureFile(file)} />
            </div>

            <div className="flex flex-col gap-2">
              <Label>3. Where to place the signature</Label>
              <Tabs value={mode} onValueChange={(value) => setMode((value as SignMode | null) ?? "placeholder")}>
                <TabsList>
                  <TabsTrigger value="placeholder">{"{{signature}}"} placeholder</TabsTrigger>
                  <TabsTrigger value="anchor">Find text on page</TabsTrigger>
                </TabsList>

                <TabsContent value="placeholder">
                  <p className="text-muted-foreground text-sm">
                    Template must contain the literal placeholder <code>{"{{signature}}"}</code> — it gets
                    replaced with the signature and today&apos;s date.
                  </p>
                </TabsContent>

                <TabsContent value="anchor" className="flex flex-col gap-3">
                  <p className="text-muted-foreground text-sm">
                    For forms without a placeholder — e.g. a blank line above a name. Enter text found on the
                    page (like part of a name) and where the signature should go relative to it.
                  </p>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="anchor-text">Text to find</Label>
                    <Input
                      id="anchor-text"
                      placeholder="e.g. วัชรากร"
                      value={anchorText}
                      onChange={(e) => setAnchorText(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label>Signature position</Label>
                    <Select
                      value={position}
                      onValueChange={(value) => setPosition((value as SignaturePosition | null) ?? "right")}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="above">Above the text</SelectItem>
                        <SelectItem value="right">Right of the text</SelectItem>
                        <SelectItem value="below">Below the text</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </TabsContent>
              </Tabs>
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="date-value">4. Date to stamp</Label>
              <Input
                id="date-value"
                type="date"
                value={dateValue}
                onChange={(e) => setDateValue(e.target.value)}
                className="w-fit"
              />
            </div>

            <Button
              size="lg"
              disabled={!templateFile || !signatureFile || signing || (mode === "anchor" && !anchorText.trim())}
              onClick={() => void handleSign()}
            >
              {signing ? "Signing..." : "Sign document automatically"}
            </Button>

            {error && <p className="text-sm text-destructive">{error}</p>}

            {placementWarning && (
              <div className="flex flex-wrap gap-2">
                <Badge variant={placementWarning.signaturePlaced ? "default" : "destructive"}>
                  {placementWarning.signaturePlaced
                    ? "Signature placed at text"
                    : "Text not found — signature placed at bottom-right"}
                </Badge>
                <Badge variant={placementWarning.datePlaced ? "default" : "destructive"}>
                  {placementWarning.datePlaced ? "Date placed" : "Date anchor not found — placed at bottom-right"}
                </Badge>
              </div>
            )}
          </CardContent>
        </Card>

        {signedPdf && (
          <Card>
            <CardHeader>
              <CardTitle>Signed document</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <iframe src={signedPdf.url} title="Signed PDF preview" className="h-[600px] w-full rounded-lg border" />
              <a href={signedPdf.url} download={signedPdf.filename}>
                <Button variant="secondary" className="w-full">
                  Download signed PDF
                </Button>
              </a>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
