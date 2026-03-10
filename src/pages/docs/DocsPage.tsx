import { useParams, Link, Navigate } from "react-router-dom";
import { getDocPage, getAdjacentPages } from "@/data/docs";
import { ArrowLeft, ArrowRight, Copy, Check, AlertTriangle, Info } from "lucide-react";
import { useState, useMemo } from "react";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      className="absolute right-2 top-2 rounded-md p-1.5 text-primary-foreground/50 hover:text-primary-foreground"
    >
      {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
    </button>
  );
}

function renderContent(content: string) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;
  let inCodeBlock = false;
  let codeLines: string[] = [];
  let codeLang = "";
  let inTable = false;
  let tableRows: string[][] = [];

  const flushTable = () => {
    if (tableRows.length > 0) {
      const headers = tableRows[0];
      const dataRows = tableRows.slice(2); // skip separator row
      elements.push(
        <div key={`table-${i}`} className="my-6 overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-secondary/50">
                {headers.map((h, j) => <th key={j} className="px-4 py-2 text-left font-medium">{h.trim()}</th>)}
              </tr>
            </thead>
            <tbody>
              {dataRows.map((row, ri) => (
                <tr key={ri} className="border-b last:border-0">
                  {row.map((cell, ci) => <td key={ci} className="px-4 py-2">{cell.trim()}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
      inTable = false;
    }
  };

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("```")) {
      if (inCodeBlock) {
        const code = codeLines.join("\n");
        elements.push(
          <div key={`code-${i}`} className="group relative my-4 rounded-lg bg-foreground text-primary-foreground">
            <CopyButton text={code} />
            <pre className="overflow-x-auto p-4 font-mono text-sm leading-relaxed"><code>{code}</code></pre>
          </div>
        );
        codeLines = [];
        inCodeBlock = false;
      } else {
        flushTable();
        codeLang = line.slice(3).trim();
        inCodeBlock = true;
      }
      i++;
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      i++;
      continue;
    }

    // Callouts
    if (line.startsWith(":::")) {
      const type = line.replace(":::", "").trim();
      const calloutLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith(":::")) {
        calloutLines.push(lines[i]);
        i++;
      }
      i++; // skip closing :::
      const isWarning = type === "warning";
      elements.push(
        <div key={`callout-${i}`} className={`my-4 flex gap-3 rounded-lg border p-4 ${isWarning ? "border-warning/30 bg-warning/5" : "border-info/30 bg-info/5"}`}>
          {isWarning ? <AlertTriangle className="h-5 w-5 shrink-0 text-warning" /> : <Info className="h-5 w-5 shrink-0 text-info" />}
          <div className="text-sm" dangerouslySetInnerHTML={{ __html: inlineFormat(calloutLines.join("\n")) }} />
        </div>
      );
      continue;
    }

    // Table
    if (line.includes("|") && line.trim().startsWith("|")) {
      const cells = line.split("|").filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      if (!inTable) inTable = true;
      tableRows.push(cells);
      i++;
      continue;
    } else if (inTable) {
      flushTable();
    }

    // Headers
    if (line.startsWith("# ")) {
      elements.push(<h1 key={`h1-${i}`} className="mb-4 text-3xl font-bold tracking-tight">{line.slice(2)}</h1>);
    } else if (line.startsWith("## ")) {
      elements.push(<h2 key={`h2-${i}`} id={line.slice(3).toLowerCase().replace(/\s+/g, "-")} className="mb-3 mt-10 scroll-mt-20 text-xl font-bold">{line.slice(3)}</h2>);
    } else if (line.startsWith("### ")) {
      elements.push(<h3 key={`h3-${i}`} id={line.slice(4).toLowerCase().replace(/\s+/g, "-")} className="mb-2 mt-6 scroll-mt-20 text-lg font-semibold">{line.slice(4)}</h3>);
    } else if (line.startsWith("---")) {
      elements.push(<hr key={`hr-${i}`} className="my-8" />);
    } else if (line.match(/^\d+\.\s/)) {
      // Ordered list item
      const text = line.replace(/^\d+\.\s/, "");
      elements.push(
        <li key={`li-${i}`} className="ml-6 list-decimal text-muted-foreground" dangerouslySetInnerHTML={{ __html: inlineFormat(text) }} />
      );
    } else if (line.startsWith("- ")) {
      elements.push(
        <li key={`li-${i}`} className="ml-6 list-disc text-muted-foreground" dangerouslySetInnerHTML={{ __html: inlineFormat(line.slice(2)) }} />
      );
    } else if (line.trim() === "") {
      elements.push(<div key={`br-${i}`} className="h-3" />);
    } else {
      elements.push(
        <p key={`p-${i}`} className="text-muted-foreground leading-relaxed" dangerouslySetInnerHTML={{ __html: inlineFormat(line) }} />
      );
    }
    i++;
  }
  flushTable();
  return elements;
}

function inlineFormat(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-foreground font-medium">$1</strong>')
    .replace(/`([^`]+)`/g, '<code class="rounded bg-secondary px-1.5 py-0.5 font-mono text-xs text-foreground">$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-primary hover:underline">$1</a>');
}

export default function DocsPage() {
  const { slug } = useParams();
  const pageSlug = slug || "introduction";
  const page = getDocPage(pageSlug);
  const { prev, next } = useMemo(() => getAdjacentPages(pageSlug), [pageSlug]);

  if (!page) return <Navigate to="/docs/introduction" replace />;

  return (
    <article>
      <div className="mb-2 text-sm text-muted-foreground">{page.category}</div>
      {renderContent(page.content)}
      <div className="mt-12 flex items-center justify-between border-t pt-6">
        {prev ? (
          <Link to={`/docs/${prev.slug}`} className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" /> {prev.title}
          </Link>
        ) : <div />}
        {next ? (
          <Link to={`/docs/${next.slug}`} className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
            {next.title} <ArrowRight className="h-4 w-4" />
          </Link>
        ) : <div />}
      </div>
    </article>
  );
}
