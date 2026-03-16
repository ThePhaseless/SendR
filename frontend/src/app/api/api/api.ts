export * from './auth.service';
import { AuthService } from './auth.service';
export * from './files.service';
import { FilesService } from './files.service';
export const APIS = [AuthService, FilesService];
