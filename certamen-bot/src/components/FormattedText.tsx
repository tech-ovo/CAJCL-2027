import React from 'react';

interface FormattedTextProps {
  text: string;
  className?: string;
}

/**
 * Parses inline markdown formatted text (**bold**, *italic*) and renders React nodes.
 * Also ensures any dangling '>' is handled cleanly if present.
 */
export const FormattedText: React.FC<FormattedTextProps> = ({ text, className }) => {
  if (!text) return null;

  // Regex to match **bold** or *italic*
  // Group 1: bold content, Group 2: italic content
  const regex = /\*\*(.+?)\*\*|\*([^\*]+?)\*/g;
  const elements: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    // Push preceding plain text
    if (match.index > lastIndex) {
      elements.push(text.slice(lastIndex, match.index));
    }

    if (match[1] !== undefined) {
      // Bold match **...**
      elements.push(
        <strong key={`b-${match.index}`} className="font-bold text-amber-200">
          {match[1]}
        </strong>
      );
    } else if (match[2] !== undefined) {
      // Italic match *...*
      elements.push(
        <em key={`i-${match.index}`} className="italic text-amber-300/90 font-serif">
          {match[2]}
        </em>
      );
    }

    lastIndex = regex.lastIndex;
  }

  // Push remaining text
  if (lastIndex < text.length) {
    elements.push(text.slice(lastIndex));
  }

  return <span className={className}>{elements}</span>;
};
