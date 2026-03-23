export * from './admin.service';
import { AdminService } from './admin.service';
export * from './altcha.service';
import { AltchaService } from './altcha.service';
export * from './auth.service';
import { AuthService } from './auth.service';
export * from './files.service';
import { FilesService } from './files.service';
export const APIS = [AdminService, AltchaService, AuthService, FilesService];
