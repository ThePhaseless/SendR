/// <reference types="jasmine" />

import { By } from '@angular/platform-browser';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, type ParamMap, Router, convertToParamMap } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../../services/auth.service';
import { AuthComponent } from './auth.component';

type AuthServiceSpy = jasmine.SpyObj<
  Pick<AuthService, 'getMe' | 'loginWithPassword' | 'requestCode' | 'setPassword' | 'verifyCode'>
>;

function createUserResponse(hasPassword: boolean) {
  return {
    email: 'user@example.com',
    has_password: hasPassword,
    id: 1,
    is_admin: false,
    is_banned: false,
    tier: 'free',
  };
}

function createAuthServiceSpy(): AuthServiceSpy {
  return jasmine.createSpyObj<
    Pick<AuthService, 'getMe' | 'loginWithPassword' | 'requestCode' | 'setPassword' | 'verifyCode'>
  >('AuthService', ['getMe', 'loginWithPassword', 'requestCode', 'setPassword', 'verifyCode']);
}

function createRouterSpy(): jasmine.SpyObj<Router> {
  return jasmine.createSpyObj<Router>('Router', ['navigate']);
}

class ParamMapStream {
  private readonly subscribers = new Set<(value: ParamMap) => void>();
  value: ParamMap;

  constructor(value: ParamMap) {
    this.value = value;
  }

  readonly observable = {
    subscribe: (next: (value: ParamMap) => void) => {
      this.subscribers.add(next);
      next(this.value);
      return {
        unsubscribe: () => {
          this.subscribers.delete(next);
        },
      };
    },
  };

  next(value: ParamMap): void {
    this.value = value;
    for (const subscriber of this.subscribers) {
      subscriber(value);
    }
  }
}

describe('AuthComponent registration password flow', () => {
  let authService: AuthServiceSpy = createAuthServiceSpy();
  let router: jasmine.SpyObj<Router> = createRouterSpy();

  beforeEach(async () => {
    authService = createAuthServiceSpy();
    router = createRouterSpy();
    router.navigate.and.resolveTo(true);

    authService.requestCode.and.returnValue(of({ message: 'Verification code sent' }));
    authService.verifyCode.and.returnValue(
      of({ expires_at: '2026-05-03T00:00:00Z', token: 'token' }),
    );
    authService.getMe.and.returnValue(of(createUserResponse(false)));
    authService.setPassword.and.returnValue(of(createUserResponse(true)));

    await TestBed.configureTestingModule({
      imports: [AuthComponent],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            queryParamMap: of(convertToParamMap({ mode: 'register' })),
            snapshot: {
              queryParamMap: convertToParamMap({ mode: 'register' }),
            },
          },
        },
        {
          provide: AuthService,
          useValue: authService,
        },
        {
          provide: Router,
          useValue: router,
        },
      ],
    }).compileComponents();
  });

  it('renders password fields in register mode', async () => {
    const fixture = TestBed.createComponent(AuthComponent);

    await fixture.whenStable();

    expect(fixture.debugElement.query(By.css('#register-password'))).not.toBeNull();
    expect(fixture.debugElement.query(By.css('#register-password-confirm'))).not.toBeNull();
  });

  it('requires a password before requesting a registration code', () => {
    const fixture = TestBed.createComponent(AuthComponent);
    const component = fixture.componentInstance;

    component.email = 'user@example.com';
    component.requestCode();

    expect(authService.requestCode).not.toHaveBeenCalled();
    expect(component.error()).toBe('Enter a password.');
  });

  it('sets the password after code verification when the account does not have one yet', () => {
    const fixture = TestBed.createComponent(AuthComponent);
    const component = fixture.componentInstance;

    component.email = 'user@example.com';
    component.password = 'password123';
    component.confirmPassword = 'password123';
    component.code = '123456';

    component.verifyCode();

    expect(authService.verifyCode).toHaveBeenCalledWith('user@example.com', '123456', true);
    expect(authService.getMe).toHaveBeenCalledTimes(1);
    expect(authService.setPassword).toHaveBeenCalledWith('password123');
    expect(router.navigate.calls.mostRecent().args).toEqual([['/']]);
  });

  it('skips password creation when the account already has one', () => {
    const fixture = TestBed.createComponent(AuthComponent);
    const component = fixture.componentInstance;

    authService.getMe.and.returnValue(of(createUserResponse(true)));
    component.email = 'user@example.com';
    component.password = 'password123';
    component.confirmPassword = 'password123';
    component.code = '123456';

    component.verifyCode();

    expect(authService.setPassword).not.toHaveBeenCalled();
    expect(router.navigate.calls.mostRecent().args).toEqual([['/']]);
  });
});

describe('AuthComponent route changes', () => {
  let queryParamMap = new ParamMapStream(convertToParamMap({ mode: 'register' }));

  beforeEach(async () => {
    queryParamMap = new ParamMapStream(convertToParamMap({ mode: 'register' }));

    await TestBed.configureTestingModule({
      imports: [AuthComponent],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            queryParamMap: queryParamMap.observable,
            snapshot: {
              queryParamMap: queryParamMap.value,
            },
          },
        },
        {
          provide: AuthService,
          useValue: {
            getMe: jasmine.createSpy('getMe').and.returnValue(of(createUserResponse(false))),
            loginWithPassword: jasmine.createSpy('loginWithPassword').and.returnValue(of({})),
            requestCode: jasmine
              .createSpy('requestCode')
              .and.returnValue(of({ message: 'Verification code sent' })),
            setPassword: jasmine
              .createSpy('setPassword')
              .and.returnValue(of(createUserResponse(true))),
            verifyCode: jasmine.createSpy('verifyCode').and.returnValue(of({})),
          },
        },
        {
          provide: Router,
          useValue: {
            navigate: jasmine.createSpy('navigate'),
          },
        },
      ],
    }).compileComponents();
  });

  it('updates the page mode when query params change on the same route', async () => {
    const fixture = TestBed.createComponent(AuthComponent);
    const component = fixture.componentInstance;

    await fixture.whenStable();

    expect(component.isRegister()).toBeTrue();
    expect(fixture.nativeElement.textContent).toContain('Create Account');

    component.password = 'password123';
    component.confirmPassword = 'password123';
    component.setMethod('password');
    await fixture.whenStable();

    expect(component.step()).toBe('password');

    queryParamMap.next(convertToParamMap({}));
    await fixture.whenStable();

    expect(component.isRegister()).toBeFalse();
    expect(component.step()).toBe('email');
    expect(component.password).toBe('');
    expect(component.confirmPassword).toBe('');
    expect(fixture.nativeElement.textContent).toContain('Sign In');
  });
});
