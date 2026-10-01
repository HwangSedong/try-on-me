import { SiteHeader } from './components/SiteHeader'
import { HomePage } from './pages/HomePage'
import { StudioPage } from './pages/StudioPage'

export default function App() {
  const fitting = window.location.pathname === '/fit' || window.location.pathname === '/fit/'
  return <>
    <SiteHeader />
    {fitting ? <StudioPage /> : <HomePage />}
  </>
}
