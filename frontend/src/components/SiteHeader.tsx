import { useEffect, useState } from 'react'

function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'))
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])
  return { theme, toggle: () => setTheme((current) => (current === 'dark' ? 'light' : 'dark')) }
}

export function SiteHeader() {
  const { theme, toggle } = useTheme()
  const fitting = window.location.pathname === '/fit' || window.location.pathname === '/fit/'
  return (
    <header className="site-header">
      <a className="brand" href="/">Try-On Me</a>
      <nav className="site-nav" aria-label="주요">
        <a href="/" aria-current={fitting ? undefined : 'page'}>홈</a>
        <a href="/fit" aria-current={fitting ? 'page' : undefined}>가상 피팅</a>
      </nav>
      <div className="header-actions">
        <button type="button" className="theme-toggle" onClick={toggle} aria-label={theme === 'dark' ? '라이트 모드로 전환' : '다크 모드로 전환'}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6" /></svg>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16.5 13.5A6.5 6.5 0 1 1 10.5 7.5 5.2 5.2 0 0 0 16.5 13.5Z" /></svg>
        </button>
      </div>
    </header>
  )
}
