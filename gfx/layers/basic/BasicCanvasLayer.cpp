/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*-
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

#include "mozilla/layers/PLayersParent.h"
#include "BasicCanvasLayer.h"
#include "gfxImageSurface.h"
#include "GLContext.h"
#include "gfxUtils.h"
#include "gfxPlatform.h"
#include "mozilla/Preferences.h"
#include "BasicLayersImpl.h"
#include "SurfaceStream.h"
#include "SharedSurfaceGL.h"
#include "SharedSurfaceEGL.h"

#include "nsXULAppAPI.h"

using namespace mozilla::gfx;
using namespace mozilla::gl;

namespace mozilla {
namespace layers {

void
BasicCanvasLayer::Initialize(const Data& aData)
{
  NS_ASSERTION(mSurface == nullptr, "BasicCanvasLayer::Initialize called twice!");

  if (aData.mSurface) {
    mSurface = aData.mSurface;
    NS_ASSERTION(!aData.mGLContext, "CanvasLayer can't have both surface and GLContext");
    mNeedsYFlip = false;
  } else if (aData.mGLContext) {
    mGLContext = aData.mGLContext;
    mIsGLAlphaPremult = aData.mIsGLAlphaPremult;
    mNeedsYFlip = true;
    MOZ_ASSERT(mGLContext->IsOffscreen(), "canvas gl context isn't offscreen");

    // [Basic Layers, non-OMTC] WebGL layer init.
    // `GLScreenBuffer::Morph`ing is only needed in BasicShadowableCanvasLayer.
  } else if (aData.mDrawTarget) {
    mDrawTarget = aData.mDrawTarget;
    mSurface = gfxPlatform::GetPlatform()->GetThebesSurfaceForDrawTarget(mDrawTarget);
    mNeedsYFlip = false;
  } else {
    NS_ERROR("CanvasLayer created without mSurface, mDrawTarget or mGLContext?");
  }

  mBounds.SetRect(0, 0, aData.mSize.width, aData.mSize.height);
}

void
BasicCanvasLayer::UpdateSurface(gfxASurface* aDestSurface, Layer* aMaskLayer)
{
  if (!IsDirty())
    return;
  Painted();

  if (mDrawTarget) {
    mDrawTarget->Flush();
    if (mDrawTarget->GetType() == BACKEND_COREGRAPHICS_ACCELERATED) {
      // We have an accelerated CG context which has changed, unlike a bitmap surface
      // where we can alias the bits on initializing the mDrawTarget, we need to readback
      // and copy the accelerated surface each frame. We want to support this for quick
      // thumbnail but if we're going to be doing this every frame it likely is better
      // to use a non accelerated (bitmap) canvas.
      mSurface = gfxPlatform::GetPlatform()->GetThebesSurfaceForDrawTarget(mDrawTarget);
    }
  }

  if (!mGLContext && aDestSurface) {
    nsRefPtr<gfxContext> tmpCtx = new gfxContext(aDestSurface);
    tmpCtx->SetOperator(gfxContext::OPERATOR_SOURCE);
    BasicCanvasLayer::PaintWithOpacity(tmpCtx, 1.0f, aMaskLayer);
    return;
  }

  if (mGLContext) {
    if (aDestSurface && aDestSurface->GetType() != gfxASurface::SurfaceTypeImage) {
      MOZ_ASSERT(false, "Destination surface must be ImageSurface type.");
      return;
    }

    nsRefPtr<gfxImageSurface> readSurf;
    nsRefPtr<gfxImageSurface> resultSurf;

    SharedSurface* sharedSurf = mGLContext->RequestFrame();
    if (!sharedSurf) {
      NS_WARNING("Null frame received.");
      return;
    }

    gfxIntSize readSize(sharedSurf->Size());
    gfxImageFormat format = (GetContentFlags() & CONTENT_OPAQUE)
                            ? gfxASurface::ImageFormatRGB24
                            : gfxASurface::ImageFormatARGB32;

    if (aDestSurface) {
      resultSurf = static_cast<gfxImageSurface*>(aDestSurface);
    } else {
      resultSurf = GetTempSurface(readSize, format);
    }
    MOZ_ASSERT(resultSurf);
    if (resultSurf->CairoStatus() != 0) {
      MOZ_ASSERT(false, "Bad resultSurf->CairoStatus().");
      return;
    }

    MOZ_ASSERT(sharedSurf->APIType() == APITypeT::OpenGL);
    SharedSurface_GL* surfGL = SharedSurface_GL::Cast(sharedSurf);

    if (surfGL->Type() == SharedSurfaceType::Basic) {
      SharedSurface_Basic* sharedSurf_Basic = SharedSurface_Basic::Cast(surfGL);
      readSurf = sharedSurf_Basic->GetData();
    } else {
      if (resultSurf->Format() == format &&
          resultSurf->GetSize() == readSize)
      {
        readSurf = resultSurf;
      } else {
        readSurf = GetTempSurface(readSize, format);
      }

      // Readback handles Flush/MarkDirty.
      mGLContext->Screen()->Readback(surfGL, readSurf);
    }
    MOZ_ASSERT(readSurf);

    bool needsPremult = surfGL->HasAlpha() && !mIsGLAlphaPremult;
    if (needsPremult) {
      gfxImageSurface* sizedReadSurf = nullptr;
      if (readSurf->Format()  == resultSurf->Format() &&
          readSurf->GetSize() == resultSurf->GetSize())
      {
        sizedReadSurf = readSurf;
      } else {
        readSurf->Flush();
        nsRefPtr<gfxContext> ctx = new gfxContext(resultSurf);
        ctx->SetOperator(gfxContext::OPERATOR_SOURCE);
        ctx->SetSource(readSurf);
        ctx->Paint();

        sizedReadSurf = resultSurf;
      }
      MOZ_ASSERT(sizedReadSurf);

      readSurf->Flush();
      resultSurf->Flush();
      gfxUtils::PremultiplyImageSurface(readSurf, resultSurf);
      resultSurf->MarkDirty();
    } else if (resultSurf != readSurf) {
      // Didn't need premult, but we do need to blit to resultSurf
      readSurf->Flush();
      nsRefPtr<gfxContext> ctx = new gfxContext(resultSurf);
      ctx->SetOperator(gfxContext::OPERATOR_SOURCE);
      ctx->SetSource(readSurf);
      ctx->Paint();
    }

    // stick our surface into mSurface, so that the Paint() path is the same
    if (!aDestSurface) {
      mSurface = resultSurf;
    }
  }
}

void
BasicCanvasLayer::Paint(gfxContext* aContext, Layer* aMaskLayer)
{
  if (IsHidden())
    return;

  FirePreTransactionCallback();
  UpdateSurface();
  FireDidTransactionCallback();

  PaintWithOpacity(aContext, GetEffectiveOpacity(), aMaskLayer);
}

void
BasicCanvasLayer::PaintWithOpacity(gfxContext* aContext,
                                   float aOpacity,
                                   Layer* aMaskLayer)
{
  NS_ASSERTION(BasicManager()->InDrawing(),
               "Can only draw in drawing phase");

  if (!mSurface) {
    NS_WARNING("No valid surface to draw!");
    return;
  }

  nsRefPtr<gfxPattern> pat = new gfxPattern(mSurface);

  pat->SetFilter(mFilter);
  pat->SetExtend(gfxPattern::EXTEND_PAD);

  gfxMatrix m;
  if (mNeedsYFlip) {
    m = aContext->CurrentMatrix();
    aContext->Translate(gfxPoint(0.0, mBounds.height));
    aContext->Scale(1.0, -1.0);
  }

  // If content opaque, then save off current operator and set to source.
  // This ensures that alpha is not applied even if the source surface
  // has an alpha channel
  gfxContext::GraphicsOperator savedOp;
  if (GetContentFlags() & CONTENT_OPAQUE) {
    savedOp = aContext->CurrentOperator();
    aContext->SetOperator(gfxContext::OPERATOR_SOURCE);
  }

  AutoSetOperator setOperator(aContext, GetOperator());
  aContext->NewPath();
  // No need to snap here; our transform is already set up to snap our rect
  aContext->Rectangle(gfxRect(0, 0, mBounds.width, mBounds.height));
  aContext->SetPattern(pat);

  FillWithMask(aContext, aOpacity, aMaskLayer);
  // Restore surface operator
  if (GetContentFlags() & CONTENT_OPAQUE) {
    aContext->SetOperator(savedOp);
  }  

  if (mNeedsYFlip) {
    aContext->SetMatrix(m);
  }
}

void
BasicShadowableCanvasLayer::Initialize(const Data& aData)
{
  BasicCanvasLayer::Initialize(aData);
  if (!HasShadow())
      return;
 
  mCanvasClient = nullptr;

  if (mGLContext) {
    GLScreenBuffer* screen = mGLContext->Screen();
    SurfaceStreamType streamType =
        SurfaceStream::ChooseGLStreamType(SurfaceStream::OffMainThread,
                                          screen->PreserveBuffer());
    SurfaceFactory_GL* factory = nullptr;
    if (!mForceReadback) {
      if (BasicManager()->GetCompositorBackendType() == mozilla::layers::LAYERS_OPENGL) {
        if (mGLContext->GetEGLContext()) {
          bool isCrossProcess = !(XRE_GetProcessType() == GeckoProcessType_Default);

          if (!isCrossProcess) {
            // [Basic/OGL Layers, OMTC] WebGL layer init.
            factory = SurfaceFactory_EGLImage::Create(mGLContext, screen->Caps());
          } else {
            // [Basic/OGL Layers, OOPC] WebGL layer init. (Out Of Process Compositing)
            // Fall back to readback.
          }
        } else {
          // [Basic Layers, OMTC] WebGL layer init.
          // Well, this *should* work...
          factory = new SurfaceFactory_GLTexture(mGLContext, mGLContext, screen->Caps());
        }
      }
    }

    if (factory) {
      screen->Morph(factory, streamType);
    }
  }
}

void
BasicShadowableCanvasLayer::Paint(gfxContext* aContext, Layer* aMaskLayer)
{
  if (!HasShadow()) {
    BasicCanvasLayer::Paint(aContext, aMaskLayer);
    return;
  }

  if (!IsDirty()) {
    return;
  }

  if (aMaskLayer) {
    static_cast<BasicImplData*>(aMaskLayer->ImplData())
      ->Paint(aContext, nullptr);
  }
  
  if (!mCanvasClient) {
    TextureFlags flags = NoFlags;
    if (mNeedsYFlip) {
      flags |= NeedsYFlip;
    }
    mCanvasClient = BasicManager()->CreateCanvasClientFor(GetCompositableClientType(), this, flags);
    if (!mCanvasClient) {
      return;
    }
    if (HasShadow()) {
      mCanvasClient->Connect();
      BasicManager()->Attach(mCanvasClient, this);
    }
  }
  
  FirePreTransactionCallback();
  mCanvasClient->Update(gfx::IntSize(mBounds.width, mBounds.height), this);

  FireDidTransactionCallback();

  BasicManager()->Hold(this);
  mCanvasClient->Updated();
}


already_AddRefed<CanvasLayer>
BasicLayerManager::CreateCanvasLayer()
{
  NS_ASSERTION(InConstruction(), "Only allowed in construction phase");
  nsRefPtr<CanvasLayer> layer = new BasicCanvasLayer(this);
  return layer.forget();
}

already_AddRefed<CanvasLayer>
BasicShadowLayerManager::CreateCanvasLayer()
{
  NS_ASSERTION(InConstruction(), "Only allowed in construction phase");
  nsRefPtr<BasicShadowableCanvasLayer> layer =
    new BasicShadowableCanvasLayer(this);
  MAYBE_CREATE_SHADOW(Canvas);
  return layer.forget();
}


}
}
