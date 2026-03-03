import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
})
export type LoginFormData = z.infer<typeof loginSchema>

export const projectCreateSchema = z.object({
  name: z.string().min(1, 'Project name is required').max(100, 'Name too long'),
  repo_url: z
    .string()
    .url('Please enter a valid URL')
    .regex(/github\.com|gitlab\.com|bitbucket\.org/, 'Must be a GitHub, GitLab, or Bitbucket URL'),
  branch: z.string().min(1, 'Branch is required').max(100, 'Branch name too long'),
})
export type ProjectCreateFormData = z.infer<typeof projectCreateSchema>

export const supportSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  email: z.string().email('Please enter a valid email'),
  subject: z.string().min(3, 'Subject must be at least 3 characters').max(200, 'Subject too long'),
  message: z.string().min(10, 'Message must be at least 10 characters').max(5000, 'Message too long'),
  category: z.enum(['general', 'bug', 'feature', 'billing']),
  priority: z.enum(['low', 'medium', 'high']),
})
export type SupportFormData = z.infer<typeof supportSchema>
