import Box from '@mui/material/Box';

type LogoProps = {
  size?: number;
  /** Цвет силуэта. По умолчанию наследуется от текста, поэтому логотип
   *  сам становится белым в тёмной теме — второй файл не нужен. */
  color?: string;
};

/**
 * Логотип-паук из public/logo.svg.
 *
 * SVG используется как маска, а не как <img>: у картинки нельзя перекрасить
 * `currentColor`, а у маски заливка задаётся фоном элемента и следует теме.
 */
export default function Logo({ size = 24, color = 'currentColor' }: LogoProps) {
  return (
    <Box
      role="img"
      aria-label="Investor"
      sx={{
        width: size,
        height: size,
        flexShrink: 0,
        backgroundColor: color,
        maskImage: 'url(/logo.svg)',
        WebkitMaskImage: 'url(/logo.svg)',
        maskSize: 'contain',
        WebkitMaskSize: 'contain',
        maskRepeat: 'no-repeat',
        WebkitMaskRepeat: 'no-repeat',
        maskPosition: 'center',
        WebkitMaskPosition: 'center',
      }}
    />
  );
}
