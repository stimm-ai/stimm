import Image from 'next/image';
import Link from 'next/link';
import logo from '@/assets/dark_theme/logo_stimm_text_only.png';

interface LogoProps {
  width?: number;
  height?: number;
  href?: string;
  className?: string;
}

export function Logo({
  width = 90,
  height = 25,
  href = '/',
  className = '',
}: LogoProps) {
  const imageElement = (
    <Image
      src={logo}
      alt="Stimm"
      width={width}
      height={height}
      className={`drop-shadow-md ${className}`}
    />
  );

  if (href) {
    return (
      <Link href={href} className="flex-shrink-0">
        {imageElement}
      </Link>
    );
  }

  return imageElement;
}
