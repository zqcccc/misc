import { permanentRedirect } from 'next/navigation'

export default function PostIndexPage() {
  permanentRedirect('/#notes')
}
